# 📺 TVMaze ETL Pipeline

A resilient, scalable data pipeline designed to ingest, normalize, and analyze TV series data from the TVMaze API. This project implements a modern **ELT (Extract, Load, Transform)** architecture using Python, enforcing strict data quality and storage efficiency.

## 🚀 Architecture Overview

The system is built on a **Medallion Architecture** pattern, processing data through three distinct layers:

### 1. Phase A: Raw Layer (Bronze) 🥉
* **Goal:** Resilient ingestion.
* **Format:** `JSONL` (Newline Delimited JSON).
* **Logic:** Fetches data from the API using **Pagination**. Implements **Exponential Backoff** (via `tenacity`) to handle HTTP 429 rate limits and network errors without crashing. Stores data with 100% fidelity to the source.

### 2. Phase B: Normalized Layer (Silver) 🥈
* **Goal:** Cleaning and Validation.
* **Format:** `Parquet` (Columnar Storage).
* **Logic:**
    * **Schema Enforcement:** Uses **Pydantic** to validate data types (e.g., ensuring ratings are floats).
    * **Sanitization:** Uses **BeautifulSoup** to strip HTML tags from summaries.
    * **Standardization:** Renames columns to `snake_case` and handles date parsing.
    * **Efficiency:** Parquet format reduces storage size by ~90% compared to JSON.

### 3. Phase C: Enriched Layer (Gold) 🥇
* **Goal:** Business Logic & Analytics.
* **Logic:**
    * **Popularity:** Categorizes shows as *Top-Rated*, *Average*, or *Low*.
    * **Availability:** Calculates "Years Active" and content freshness.
    * **Genre Analysis:** Explodes complex arrays to calculate average ratings per genre.

---

## 🛠️ Project Structure

```text
tvmaze_etl/
├── .github/
│   └── workflows/
│       └── daily_etl.yml    # Orchestration configuration
├── data/
│   ├── raw/                 # Contains raw .jsonl files
│   └── normalized/          # Contains processed .parquet files
├── src/
│   ├── pipeline.py          # Main ETL script (Phase A + B)
│   └── enrichment.py        # Analytics script (Phase C)
├── requirements.txt         # Project dependencies
└── README.md                # Documentation
