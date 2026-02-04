# 📐 Entity Relationship Diagram (ERD)

This document outlines the schema of the data at each stage of the pipeline.

**Note:** The relationship between `enriched_shows` and `genre_stats` is logically handled via an **Unnest/Explode** operation on the `genres` array.

```mermaid
erDiagram
    %% Raw Data Layer
    %% Ingested directly from JSONL
    raw_shows {
        INTEGER id
        STRING name
        STRING type
        STRING language
        STRING[] genres
        STRING status
        INTEGER runtime
        STRING premiered
        STRUCT rating
        STRING summary
        INTEGER updated
        STRING _links
    }

    %% Normalized Layer
    %% Cleaned, Validated, Type-Cast
    normalized_shows {
        INTEGER id PK
        STRING name
        STRING type
        STRING language
        STRING[] genres
        STRING status
        FLOAT runtime
        DATE premiere_date
        FLOAT rating
        STRING summary
    }

    %% Enriched Layer (The Gold Table)
    %% Contains ALL normalized data + Business Logic
    enriched_shows {
        INTEGER id PK
        STRING name
        STRING type
        STRING language
        STRING[] genres
        STRING status
        FLOAT runtime
        DATE premiere_date
        FLOAT rating
        STRING summary
        %% Derived Columns Below %%
        INTEGER years_since_premiere "Derived"
        BOOLEAN is_active "Derived"
        STRING popularity_category "Derived"
    }

    %% Logical View: Exploded Genres
    %% Represents the UNNEST(genres) operation for analysis
    show_genres_exploded {
        INTEGER show_id FK
        STRING genre_name
    }

    %% Analytics Layer
    %% Aggregated Statistics
    genre_stats {
        STRING genre_name PK
        FLOAT avg_rating "Aggregated"
        INTEGER show_count "Aggregated"
    }

    %% Data Flow Relationships
    raw_shows ||--|| normalized_shows : "Clean & Validate"
    normalized_shows ||--|| enriched_shows : "Enrich Business Logic"
    
    %% The Analytical Join Logic
    enriched_shows ||--|{ show_genres_exploded : "1. UNNEST(genres)"
    show_genres_exploded }|--|| genre_stats : "2. GROUP BY genre"
