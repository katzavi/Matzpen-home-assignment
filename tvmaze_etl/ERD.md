# 📐 Entity Relationship Diagram (ERD)

This document outlines the schema of the actual data artifacts created by the pipeline.

**Note:** The `genre_stats` table is a derived view created by exploding the `genres` array in the Enriched layer.

```mermaid
erDiagram
    %% Raw Data Layer (JSONL)
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

    %% Normalized Layer (Parquet)
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

    %% Enriched Layer (Parquet/DataFrame)
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
        %% Derived Columns %%
        INTEGER years_since_premiere "Calculated"
        BOOLEAN is_active "Calculated"
        STRING popularity_category "Calculated"
    }

    %% Analytics View (Final Report)
    genre_stats {
        STRING genre_name PK
        FLOAT avg_rating "Aggregated"
        INTEGER show_count "Aggregated"
    }

    %% Relationships & Transformations
    raw_shows ||--|| normalized_shows : "Clean & Validate"
    normalized_shows ||--|| enriched_shows : "Enrich"
    
    %% Accurate Description of the Transformation
    enriched_shows ||--|{ genre_stats : "TRANSFORM: Explode(genres) -> GroupBy"
