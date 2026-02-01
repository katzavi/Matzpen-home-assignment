import requests
import json
import logging
import polars as pl
import duckdb
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# --- CONFIGURATION ---
API_URL = "https://api.tvmaze.com/shows"
# Define paths relative to the script execution
BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
NORM_DIR = BASE_DIR / "data" / "normalized"
ENRICHED_DIR = BASE_DIR / "data" / "enriched"
DB_DIR = BASE_DIR / "data" / "db"
MIN_ITEMS = 250

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    force=True
)
logger = logging.getLogger("TVMazePipeline")

# --- DATA MODELS (Phase B: Validation) ---
class TVShow(BaseModel):
    id: int
    name: str
    type: str
    language: Optional[str] = None
    genres: List[str] = []
    status: str
    runtime: Optional[float] = None  # Float to be safe
    
    # Aliasing: Map API's 'premiered' to our 'premiere_date'
    premiere_date: Optional[Any] = Field(alias="premiered", default=None)
    
    rating: Optional[float] = None
    summary: Optional[str] = None

    # Validator 1: Clean HTML from summary
    @field_validator('summary', mode='before')
    def clean_html_tags(cls, v):
        if not v:
            return None
        return BeautifulSoup(v, "html.parser").get_text()

    # Validator 2: Extract nested rating (e.g., {'average': 6.5} -> 6.5)
    @field_validator('rating', mode='before')
    def extract_rating_value(cls, v):
        if isinstance(v, dict):
            return v.get('average')
        return v
    
    # Validator 3: Ensure dates are standard (Handle Nulls)
    @field_validator('premiere_date', mode='before')
    def parse_date(cls, v):
        if not v:
            return None
        return v  # We will let Polars handle the final date conversion

    model_config = ConfigDict(populate_by_name=True)

# --- THE PIPELINE CLASS ---
class TVMazePipeline:
    def __init__(self):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        NORM_DIR.mkdir(parents=True, exist_ok=True)
        ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.db_path = DB_DIR / "tvmaze.duckdb"

    def _is_network_error(self, ex):
        return isinstance(ex, requests.exceptions.RequestException)

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5)
    )
    def fetch_page(self, page_num):
        """Fetch a single page from API with retry logic."""
        logger.info(f"Fetching Page {page_num}...")
        resp = requests.get(API_URL, params={'page': page_num}, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def run(self):
        # --- PHASE A: RAW INGESTION ---
        all_raw_data = []
        page = 0
        
        logger.info("--- Starting Phase A: Raw Ingestion ---")
        while len(all_raw_data) < MIN_ITEMS:
            try:
                data = self.fetch_page(page)
                if not data: break # Stop if empty
                all_raw_data.extend(data)
                page += 1
            except Exception as e:
                logger.error(f"Fatal error on page {page}: {e}")
                break
        
        # Save Raw Data as JSONL (Efficient line-by-line JSON)
        raw_file = RAW_DIR / f"shows_raw_{self.timestamp}.jsonl"
        with open(raw_file, 'w', encoding='utf-8') as f:
            for entry in all_raw_data:
                f.write(json.dumps(entry) + "\n")
        
        logger.info(f"Phase A Complete. Saved {len(all_raw_data)} raw records to {raw_file.name}")

        # --- PHASE B: NORMALIZATION ---
        logger.info("--- Starting Phase B: Normalization ---")
        df_normalized = self.process_normalization(all_raw_data)

        # --- PHASE C: ENRICHMENT ---
        logger.info("--- Starting Phase C: Enrichment ---")
        self.process_enrichment(df_normalized)

        # --- PHASE D: LOADING TO DUCKDB ---
        logger.info("--- Starting Phase D: Loading to DuckDB ---")
        norm_file = NORM_DIR / f"shows_normalized_{self.timestamp}.parquet"
        self.load_to_duckdb(raw_file, norm_file)

    def process_normalization(self, raw_data):
        valid_records = []
        
        for item in raw_data:
            try:
                # Pydantic does the validation & cleaning here
                show = TVShow(**item)
                valid_records.append(show.model_dump())
            except ValidationError as e:
                # In production, we would log this to a 'Dead Letter Queue' file
                continue

        # Convert to Polars DataFrame for efficient storage
        df = pl.DataFrame(valid_records)

        # Ensure Date Column is actual Date Type (not string)
        df = df.with_columns(pl.col("premiere_date").str.to_date(strict=False))

        # Save as Parquet (Optimized for DuckDB)
        output_file = NORM_DIR / f"shows_normalized_{self.timestamp}.parquet"
        df.write_parquet(output_file)
        
        logger.info(f"Phase B Complete. Saved {len(df)} clean records to {output_file.name}")
        return df

    def process_enrichment(self, df: pl.DataFrame):
        # 1. Content Availability: Years since air & Active status
        # We assume 'status' == 'Running' means active.
        current_year = datetime.now().year
        
        df_enriched = df.with_columns([
            (current_year - pl.col("premiere_date").dt.year()).alias("years_since_premiere"),
            (pl.col("status") == "Running").alias("is_active")
        ])

        # 2. Popularity Classification
        # Logic: > 8.0 = Top-Rated, < 5.0 = Low, else Average
        df_enriched = df_enriched.with_columns(
            pl.when(pl.col("rating") >= 8.0).then(pl.lit("Top-Rated"))
            .when(pl.col("rating") < 5.0).then(pl.lit("Low"))
            .otherwise(pl.lit("Average"))
            .alias("popularity_category")
        )

        # 3. Genre Analysis (Aggregation Layer)
        # We explode the list of genres to calculate stats per genre
        genre_stats = (
            df_enriched.explode("genres")
            .group_by("genres")
            .agg(pl.col("rating").mean().alias("avg_genre_rating"))
            .sort("avg_genre_rating", descending=True)
        )

        # Save Enriched Data
        enriched_file = ENRICHED_DIR / f"shows_enriched_{self.timestamp}.parquet"
        df_enriched.write_parquet(enriched_file)
        
        # Save Genre Stats (Analytics)
        stats_file = ENRICHED_DIR / f"genre_stats_{self.timestamp}.parquet"
        genre_stats.write_parquet(stats_file)

        logger.info(f"Phase C Complete. Saved enriched data and genre stats to {ENRICHED_DIR.name}")

    def load_to_duckdb(self, raw_file, norm_file):
        """Load generated files into DuckDB tables."""
        con = duckdb.connect(str(self.db_path))
        
        # Load Raw Data (JSONL)
        con.execute("DROP TABLE IF EXISTS raw_shows")
        con.execute(f"CREATE TABLE raw_shows AS SELECT * FROM read_json_auto('{raw_file}')")
        
        # Load Normalized Data (Parquet)
        con.execute("DROP TABLE IF EXISTS normalized_shows")
        con.execute(f"CREATE TABLE normalized_shows AS SELECT * FROM read_parquet('{norm_file}')")
        
        logger.info(f"DuckDB Load Complete. Tables 'raw_shows' and 'normalized_shows' created in {self.db_path.name}")
        con.close()

if __name__ == "__main__":
    pipeline = TVMazePipeline()
    pipeline.run()