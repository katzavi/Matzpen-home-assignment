# 📺 TVMaze ETL Pipeline

A resilient, scalable data pipeline designed to ingest, normalize, and analyze TV series data from the TVMaze API. This project implements a modern **ELT (Extract, Load, Transform)** architecture using Python, enforcing strict data quality and storage efficiency.

---

## 🚀 Architecture & Logic

The system is built on the **Medallion Architecture** pattern (Bronze $\rightarrow$ Silver $\rightarrow$ Gold), processing data through three distinct layers of quality.

### 🥉 Phase A: Raw Layer (The "Bronze" Layer)
**Goal:** Create an immutable, high-fidelity backup of the source data.

* **Ingestion Logic:**
    * **Pagination:** The script intelligently iterates through API pages (`page=0`, `page=1`...) until it collects the required minimum of 250 series. This ensures memory stability even if fetching thousands of records.
    * **Resiliency (Tenacity):** We utilize the `tenacity` library to implement **Exponential Backoff**. If the API returns a `429 Too Many Requests` or a `500 Server Error`, the script pauses (2s, 4s, 8s...) and retries automatically instead of crashing.
* **Storage Format: JSONL (Newline Delimited JSON)**
    * We store data in `.jsonl` format. Unlike a standard JSON array (which requires loading the whole file to read), JSONL allows for **streaming** reads and writes, making it infinitely scalable for raw ingestion.

### 🥈 Phase B: Normalized Layer (The "Silver" Layer)
**Goal:** Clean, validate, and enforce a strict schema.

* **Validation Logic (The "Gatekeeper"):**
    * We use **Pydantic** to define a strict Data Model. Every single record from the Raw layer is passed through this validator.
    * **Type Safety:** Fields like `rating` are coerced to `float`. If the API sends garbage data (e.g., `"rating": "TBD"`), the record is flagged and excluded from the clean dataset to prevent downstream failures.
* **Cleaning Logic:**
    * **HTML Parsing:** The API returns summaries with HTML tags (`<p><b>...`). We use a custom Pydantic Validator with **BeautifulSoup** to strip these tags, leaving only clean, human-readable text.
    * **Standardization:** All column names are mapped to `snake_case` (e.g., `premiered` $\rightarrow$ `premiere_date`).
* **Storage Format: Parquet**
    * Data is saved as **Apache Parquet**. This is a **columnar** storage format that compresses data by ~90% compared to JSON. It allows analytical queries to scan only the columns they need (e.g., just "Rating") without reading the heavy "Summary" text, resulting in massive performance gains.

### 🥇 Phase C: Enriched Layer (The "Gold" Layer)
**Goal:** Derive business insights and aggregations.

* **Enrichment Logic:**
    * **Popularity Classifier:** A calculated column categorizes shows into `Top-Rated` (>8), `Average` (6-8), or `Low` (<6).
    * **Content Freshness:** Calculates the `years_since_premiere` to analyze the age distribution of the content.
* **Analytics:**
    * **Genre Analysis:** Since shows can have multiple genres (e.g., `["Drama", "Sci-Fi"]`), we use an "Explode" operation to flatten the list and calculate the exact average rating per individual genre.

---

## 🛠️ Project Structure

```text
tvmaze_etl/
├── .github/
│   └── workflows/
│       └── daily_etl.yml    # GitHub Actions Orchestration
├── data/
│   ├── raw/                 # Bronze Layer (JSONL)
│   └── normalized/          # Silver Layer (Parquet)
├── src/
│   ├── pipeline.py          # Phases A & B (Ingest + Normalize)
│   └── enrichment.py        # Phase C (Analytics & Reporting)
├── requirements.txt         # Python dependencies
└── README.md                # Project Documentation

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

## ⏱️ Orchestration (Automated Scheduling)

The pipeline is automated using **GitHub Actions**, removing the need for local execution. It handles the entire lifecycle: checking out code, setting up Python, running the ETL, and committing the results back to the repository.

### ⚙️ How to Setup & Trigger

**1. Enable Permissions (One-time Setup)**
To allow the "Actions Bot" to save data back to your repository, you must enable write permissions:
1.  Go to your repository **Settings**.
2.  Navigate to **Actions** → **General**.
3.  Scroll to "Workflow permissions" and select **"Read and write permissions"**.
4.  Click **Save**.

**2. Manual Trigger (For Testing)**
You don't have to wait for the daily schedule to verify it works:
1.  Go to the **Actions** tab in this repository.
2.  Select **"Daily TVMaze ETL"** from the sidebar.
3.  Click the **"Run workflow"** button.
4.  Wait ~60 seconds for the job to complete.

**3. Automatic Schedule**
* **Frequency:** Runs automatically every day at **08:00 UTC**.
* **Configuration:** Defined in `.github/workflows/daily_etl.yml`.

### ✅ Verification
After a successful run (manual or scheduled), the GitHub Actions Bot will automatically create a new commit.
* **Check the commit history:** You will see a commit titled `🤖 Automated Data Update`.
* **Check the files:** Navigate to `data/raw` or `data/normalized` to see the newly generated files (e.g., `shows_raw_2023...jsonl`).

### Configuration (`.github/workflows/daily_etl.yml`)
```yaml
name: Daily TVMaze ETL
on:
  schedule:
    - cron: '0 8 * * *' # Runs at 08:00 UTC daily
  workflow_dispatch:    # Allows manual testing

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: python src/pipeline.py
      - name: Commit Data
        run: |
          git config --global user.name "GitHub Actions Bot"
          git config --global user.email "actions@github.com"
          git add data/
          git commit -m "🤖 Automated Data Update" || exit 0
          git push
```
The following configuration ensures the pipeline only runs when manually triggered via the GitHub UI (`workflow_dispatch`), preventing unwanted automatic runs.

```yaml
name: TVMaze ETL (Manual)

on:
  # Allows manual triggering from the Actions tab
  workflow_dispatch:

permissions:
  contents: write

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run ETL Pipeline
        run: python src/pipeline.py

      - name: Commit and Push Data
        run: |
          git config --global user.name "GitHub Actions Bot"
          git config --global user.email "actions@github.com"
          git add data/
          # Only commit if data changed
```          
