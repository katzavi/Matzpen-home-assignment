# Software Architecture Diagram

This diagram illustrates the end-to-end data flow of the TVMaze ETL pipeline, highlighting the interaction between the Python application, the File System (Data Lake), and the DuckDB Warehouse.

## 🔄 Process Flow: Step-by-Step

The following steps describe the lifecycle of a data packet moving through the TVMaze ETL pipeline:

### 1. Orchestration Trigger ⏱️
* **Action:** The pipeline is triggered manually via GitHub Actions (or on a schedule).
* **System:** A temporary Ubuntu Linux container spins up.
* **Logic:** The environment installs Python 3.9 and dependencies (`pandas`, `tenacity`, `pydantic`).

### 2. Extraction (Resilient API Calls) 📡
* **Action:** The `TVMazePipeline` class initializes.
* **Logic:** It calls the `GET /shows` API endpoint.
    * **Pagination:** Iterates page by page (`page=0`, `page=1`...) until 250+ items are collected.
    * **Resiliency:** If the API returns a `429` (Rate Limit) or `500` (Server Error), the `tenacity` library waits exponentially (2s, 4s, 8s...) and retries automatically.

### 3. Raw Data Persistence (The Bronze Layer) 🥉
* **Action:** Data is written to disk immediately.
* **Format:** `.jsonl` (Newline Delimited JSON).
* **Why:** This creates an immutable backup of the exact API response. If downstream processing fails, we can replay this file without re-fetching from the internet.

### 4. Validation & Cleaning (The Gatekeeper) 🛡️
* **Action:** The pipeline reads the Raw JSONL and passes every record through a **Pydantic Model**.
* **Logic:**
    * **Type Checking:** Ensures `id` is an integer and `rating` is a float. Malformed records are dropped/logged.
    * **Sanitization:** Uses **BeautifulSoup** to strip HTML tags (e.g., `<p><b>`) from the summary field.
    * **Standardization:** Renames columns to `snake_case` (e.g., `premiered` → `premiere_date`).

### 5. Normalization (The Silver Layer) 🥈
* **Action:** Validated data is converted to a DataFrame and saved.
* **Format:** `.parquet` (Apache Parquet).
* **Why:**
    * **Compression:** Reduces file size by ~90%.
    * **Performance:** Columnar storage allows analytical queries to skip reading heavy text columns.
    * **Schema Enforcement:** Unlike JSON, Parquet strictly enforces data types (Date, Float, String).

### 6. Business Enrichment (The Gold Layer) 🥇
* **Action:** The `enrichment.py` script loads the Parquet file.
* **Logic:** It applies business rules to derive new insights:
    * **Popularity:** Categorizes shows as "Top-Rated" (>8), "Average" (6-8), or "Low" (<6).
    * **Longevity:** Calculates `years_since_premiere` based on the current date.

### 7. Analytical Transformation 📊
* **Action:** Generates the Genre Report.
* **Logic:**
    * **Explode:** Since a show has multiple genres (`['Drama', 'Sci-Fi']`), the system "explodes" the array so the show appears once per genre.
    * **Aggregation:** Groups by `genre` and calculates the average rating.

### 8. Data Publication 🚀
* **Action:** The GitHub Action detects the new files in `data/raw` and `data/normalized`.
* **System:** It performs a `git commit` and `git push` back to the repository.
* **Result:** The new data is available for analysts to query via DuckDB or SQLTools immediately.
* 
```mermaid
flowchart TD
    %% Styles
    classDef external fill:#f9f,stroke:#333,stroke-width:2px;
    classDef process fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef storage fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef db fill:#fff3e0,stroke:#ef6c00,stroke-width:2px;

    %% External Source
    API[("TVMaze API\n(REST Endpoint)")]:::external

    %% Application Layer
    subgraph App["TVMazePipeline (Python)"]
        direction TB
        Fetcher["Page Fetcher\n(Requests + Tenacity)"]:::process
        Ingester["Raw Ingester\n(DuckDB SQL)"]:::process
        Normalizer["Normalizer\n(Pydantic + Polars)"]:::process
        Enricher["Enricher\n(Polars)"]:::process
    end

    %% Storage Layer (Data Lake)
    subgraph DataLake["File System (Data Lake)"]
        JSONL["shows_raw_*.jsonl\n(Bronze)"]:::storage
        ParquetNorm["shows_normalized_*.parquet\n(Silver)"]:::storage
        ParquetEnrich["shows_enriched_*.parquet\n(Gold)"]:::storage
        ParquetStats["genre_stats_*.parquet\n(Gold)"]:::storage
    end

    %% Database Layer (Warehouse)
    subgraph Warehouse["DuckDB (tvmaze.duckdb)"]
        TblRaw[("raw_shows\n(SCD Type 2)")]:::db
        TblNorm[("normalized_shows")]:::db
        TblEnrich[("enriched_shows")]:::db
        TblStats[("genre_stats")]:::db
    end

    %% Data Flow - Phase A
    API -->|"1. Fetch Pages"| Fetcher
    Fetcher -->|"2. Write Stream"| JSONL
    JSONL -.->|"3. read_json_auto"| Ingester
    Ingester -->|"4. Merge & Version"| TblRaw
    
    %% Data Flow - Phase B
    TblRaw -.->|"5. Fetch (is_latest=True)"| Normalizer
    Normalizer -->|"6. Validate & Clean"| ParquetNorm
    ParquetNorm -.->|"7. read_parquet"| TblNorm
    
    %% Data Flow - Phase C
    TblNorm -.->|"8. Fetch"| Enricher
    Enricher -->|"9. Calc Metrics"| ParquetEnrich
    Enricher -->|"9. Aggregate"| ParquetStats
    
    ParquetEnrich -.->|"10. read_parquet"| TblEnrich
    ParquetStats -.->|"10. read_parquet"| TblStats
```
