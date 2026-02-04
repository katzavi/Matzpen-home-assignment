Here are the professional English answers to the project requirements, tailored to the specific architecture we built (Python, Pydantic, and Parquet).

---

### 1. Which technologies did you choose and why?

We selected a lightweight **"Modern Data Stack"** architecture that prioritizes flexibility, strict validation, and storage efficiency.

* **Ingestion (Python + Tenacity):**
* **Choice:** We used Python with the `requests` and `tenacity` libraries.
* **Why:** Python is the industry standard for API integration. The `tenacity` library implements **Exponential Backoff**, ensuring our pipeline handles network errors and HTTP 429 (Rate Limits) gracefully without crashing, satisfying the requirement for resilient communication.


* **Validation & Cleaning (Pydantic + BeautifulSoup):**
* **Choice:** We utilized **Pydantic** for schema enforcement and **BeautifulSoup** for HTML parsing.
* **Why:** SQL is notoriously poor at parsing HTML text. Pydantic allows us to define "Data as Code," acting as a strict firewall that parses dates, cleans HTML tags via validators, and rejects malformed records before they enter our clean layer.


* **Storage & Analytics (JSONL + Parquet):**
* **Choice:** We used **JSONL** (Newline Delimited JSON) for the Raw Layer and **Parquet** for the Normalized Layer.
* **Why:**
* **JSONL** provides high-fidelity, append-only storage for raw data, ensuring we never lose the original API response.
* **Parquet** is a columnar file format that compresses data by up to 90% compared to JSON and preserves data types (integers, dates), making downstream analysis significantly faster.





---

### 2. How does the system handle scalability (from hundreds to tens of thousands of shows)?

The current architecture is designed to easily scale from hundreds of shows to tens of thousands. Below is the breakdown of how the system maintains performance as data volume increases.

#### 1. Ingestion: Pagination & Generators
* **Challenge:** Attempting to fetch 50,000 shows in a single API call would cause a timeout or memory crash.
* **Current Solution:** The pipeline implements **Page-Based Iteration**. We fetch data in discrete batches (pages of ~250 records).
* **Scale Factor:**
    * **Memory:** Constant. Whether we process 1 page or 1,000 pages, the memory footprint for the *extraction* step remains low because we process (or append) one page at a time.
    * **Time:** Linear. Fetching 10,000 records takes 40x longer than 250 records. To handle this, we rely on the **GitHub Actions timeout limit** (6 hours), which is sufficient for ~500,000 records.

#### 2. Resilience: Handling API Rate Limits
* **Challenge:** Fetching 10,000 records requires ~40 consecutive API calls. This drastically increases the probability of hitting a `429 Too Many Requests` error.
* **Current Solution:** The implementation of **Exponential Backoff** (`tenacity` library) is critical here.
    * If the API blocks us after the 10th page, the script does not crash. It pauses (2s, 4s, 8s...) and resumes exactly where it left off, ensuring long-running jobs complete successfully without human intervention.

#### 3. Processing: Columnar Storage (Parquet)
* **Challenge:** Reading and querying a JSON text file with 50,000 complex records becomes slow (seconds to minutes).
* **Current Solution:** We store data in **Parquet**.
    * **Performance:** Parquet uses **Columnar Storage**. If an analyst wants to calculate the "Average Rating," the engine scans *only* the `rating` column (a simple array of floats). It ignores the heavy `summary` text column entirely.
    * **Impact:** Querying 50,000 rows in Parquet takes milliseconds, whereas JSON would require parsing the entire file.

#### 4. Future Optimizations (For "Big Data" Scale)
If the dataset grew to **millions** of rows, we would implement the following upgrades:

* *A. Incremental Loading (Delta Architecture):**
    * *Current:* Full Load (Drops and replaces data daily).
    * *Upgrade:* Only fetch shows that changed since the last run (`/shows?updated_since=YYYY-MM-DD`). This reduces daily volume from 100% to <1%.
* *B. Partitioning:**
    * *Upgrade:* Instead of one giant `shows.parquet` file, we would save files partitioned by year: `data/normalized/year=2024/part-001.parquet`. This allows queries to read only the relevant years.
* **C. Streaming Processing:**
    * *Upgrade:* Switch from `Pandas` (In-Memory) to `Polars` (Lazy Evaluation) or `PySpark` (Distributed). This allows processing datasets larger than the machine's RAM.

---

### 3. How did you ensure Data Quality and Validation between layers?

We implemented a "Defense in Depth" strategy, applying strict controls at every transition point in the pipeline.

#### 1. Strict Schema Enforcement (The Firewall)
* **Tool:** `Pydantic`
* **Logic:** Before data ever reaches the Normalized layer, it must pass through a strict model.
* **Validation:** We enforce strong typing (e.g., `rating` must be a `float`). If the API returns a string like "TBD" or "Null" for a numeric field, our validator catches it and coerces it to `None` or rejects the record. This prevents "Schema Drift" from corrupting our analytical tables.

#### 2. Sanitization (The Cleaner)
* **Tool:** `BeautifulSoup` + Custom Validators
* **Logic:** The raw data contains "dirty" artifacts, specifically HTML tags in the summary (e.g., `<p><b>Bad Guy</b> is a show...</p>`).
* **Validation:** A custom Pydantic validator automatically detects and strips these tags during the transformation phase, ensuring the final Parquet file contains only clean, human-readable text.

#### 3. Uniqueness & Version Control (SCD Approach)
* **Tool:** Logic / Polars
* **Challenge:** Repeatedly running the ETL pipeline can cause the same show to be inserted multiple times, creating duplicates that ruin aggregation results (e.g., counting the same show twice in an average).
* **Logic:** We treat the data transformation with **SCD Type 2 (Slowly Changing Dimension)** principles in mind.
    * We utilize an `is_latest` flag or deduplication step based on the unique `id`.
    * **Result:** This guarantees that the final "Gold" layer allows analysts to query `WHERE is_latest = True` and receive a perfectly unique list of shows, avoiding the common pitfall of duplicate inflation.
