# Software Architecture Diagram

This diagram illustrates the end-to-end data flow of the TVMaze ETL pipeline, highlighting the interaction between the Python application, the File System (Data Lake), and the DuckDB Warehouse.

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