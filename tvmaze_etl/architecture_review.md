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

The architecture is designed for **Horizontal Scalability** and efficient resource management:

* **Pagination & Streaming (Memory Management):**
The ingestion script does not attempt to load the entire database into RAM at once. It utilizes **Pagination**, fetching data in small batches (pages) and writing them to disk immediately. This ensures the system runs with a low, constant memory footprint, whether processing 200 shows or 200,000 shows.
* **Columnar Storage (Read Efficiency):**
By converting data to **Parquet** in the Normalized Layer, we enable "Column Pruning." As the dataset grows, analytical queries (e.g., calculating average ratings) only need to scan the specific `rating` column, ignoring heavy text columns like `summary`. This makes queries exponentially faster than scanning a standard JSON or CSV file.
* **Decoupled Storage:**
We adopted a **Data Lake** approach (File-based storage). Since storage (Disk/S3) is separated from compute, the dataset can grow indefinitely without requiring database server upgrades. If processing becomes too slow in the future, the processing engine can be swapped from a single Python script to a distributed framework like **Spark** without changing the underlying data format.

---

### 3. How did you ensure Data Quality and Validation between layers?

We implemented a **"Defense in Depth"** strategy to ensure quality at every stage:

* **The "Gatekeeper" Pattern (Pydantic):**
Between the Raw and Normalized layers, every record must pass through a strict **Pydantic Model**.
* **Type Safety:** We enforce that `rating` is a float and `id` is an integer.
* **Sanitization:** Custom validators automatically strip HTML tags from the `summary` field and standardize the `premiere_date` format.
* **Rejection:** Records that fail validation are caught in a `try/except` block and logged, preventing a single bad record from crashing the entire pipeline.


* **Immutability (Raw Layer):**
We strictly adhere to the **Bronze/Raw Layer** principle. The data from the API is saved exactly as received (including errors) in JSONL format. This provides a safety net: if a bug is discovered in our cleaning logic later, we can always replay the raw data without re-fetching from the API.
* **Schema Enforcement (Parquet):**
Unlike JSON, which is schema-less, the final **Parquet** files enforce a rigid schema. A column defined as `Date` physically cannot store a string text. This guarantees that the "Enriched Layer" (Phase C) consumes 100% structurally correct data, eliminating common analysis errors.