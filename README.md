# TVMaze ETL Pipeline

A robust ETL (Extract, Transform, Load) pipeline that ingests TV show data from the TVMaze API, processes it using Python (Polars, Pydantic), and stores it in a DuckDB database for analytics.

## Features

- **Robust Ingestion**: Fetches data with automatic retries and pagination handling.
- **Versioning**: Implements "Slowly Changing Dimension" Type 2-like logic in DuckDB to track data versions (`version`, `is_latest`).
- **Data Quality**: Validates and cleans data using Pydantic models (HTML stripping, type casting).
- **High Performance**: Uses Polars for fast in-memory processing and Parquet for intermediate storage.
- **Embedded Database**: Uses DuckDB as the central data warehouse.
- **Enrichment**: Calculates derived metrics (show age, active status) and aggregates genre statistics.

## Project Structure

```
tvmaze_etl/
├── data/
│   ├── raw/            # Raw JSONL files
│   ├── normalized/     # Cleaned Parquet files
│   ├── enriched/       # Enriched Parquet files
│   └── db/             # DuckDB database file (tvmaze.duckdb)
├── src/
│   └── pipeline.py     # Main ETL script
└── README.md
```

## Prerequisites

- Python 3.9+
- Virtual Environment (recommended)

## Installation

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install requests polars duckdb pydantic beautifulsoup4 tenacity
```

## Usage

Run the pipeline:

```bash
python3 src/pipeline.py
```

### Configuration
You can modify `src/pipeline.py` to adjust settings:
- `MIN_PAGES`: Number of pages to fetch (set to `None` for all).

## Pipeline Phases

1.  **Phase A: Raw Ingestion**
    - Fetches data from TVMaze API.
    - Saves raw JSONL.
    - Loads into DuckDB `raw_shows` table with version control.

2.  **Phase B: Normalization**
    - Fetches `is_latest=True` records from DuckDB.
    - Validates schema with Pydantic.
    - Cleans HTML from summaries.
    - Standardizes dates.
    - Saves to `normalized_shows` table.

3.  **Phase C: Enrichment**
    - Calculates `years_since_premiere` and `is_active`.
    - Categorizes popularity (Top-Rated, Average, Low).
    - Generates `genre_stats`.
    - Saves to `enriched_shows` and `genre_stats` tables.

## Querying Data

You can query the generated DuckDB database using the CLI or Python:

```bash
duckdb data/db/tvmaze.duckdb "SELECT * FROM genre_stats LIMIT 5"
```