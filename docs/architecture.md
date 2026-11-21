# Architecture

```mermaid
flowchart LR
    subgraph Sources["Public sources (OGL – Alberta)"]
        CKAN["open.alberta.ca CKAN<br/>enrolment XLSX ×20<br/>capacity XLSX ×1"]
        GIS["geospatial.alberta.ca ArcGIS<br/>public + separate boundaries"]
        EPSB["EPSB FeatureServer<br/>school points (optional)"]
    end

    subgraph Pipeline["backend/pipeline (Typer CLI: abcap)"]
        DL["download<br/>manifest.json + SHA-256"]
        LOAD["extract/load<br/>Pandas, GeoPandas"]
        DBT["dbt build<br/>staging → marts + tests"]
        DQ["quality checks"]
        FC["forecast<br/>statsmodels Holt"]
    end

    subgraph DB["PostgreSQL 18 + PostGIS"]
        RAW[(raw)]
        STG[(staging)]
        MART[(mart<br/>star schema)]
        OPS[(ops<br/>pipeline_run, dq_result)]
    end

    API["FastAPI /api/v1"]
    WEB["Next.js dashboard"]

    CKAN --> DL
    GIS --> DL
    EPSB --> DL
    DL --> LOAD --> RAW --> DBT --> STG --> MART
    DBT --> DQ --> OPS
    MART --> FC --> MART
    LOAD -. run_id .-> OPS
    MART --> API --> WEB
    OPS --> API
```

**Status (Phase 2):** built so far: download, extract/load into `raw` (Pandas, GeoPandas), the independent row-count check, `ops.pipeline_run`, dbt staging and the `mart` star schema with 58 tests, Compose (db and backend) and `/api/v1/health`. Quality checks, forecasts and the dashboard follow in Phases 3 to 6.

### dbt lineage

```mermaid
flowchart LR
    RE[raw.enrolment_school] --> SE[stg_enrolment__school] --> SG[stg_enrolment__school_grade]
    RA[raw.enrolment_authority] --> SA[stg_enrolment__authority]
    RC[raw.capacity] --> SC[stg_capacity__facility_row] --> M[int_capacity__matched]
    M --> G[int_capacity__grouped] --> GR[int_capacity__group]
    SE --> M
    CW[(seed: crosswalk)] --> M
    RB[raw.authority_boundary] --> SB[stg_geo__authority_boundary]
    RP[raw.school_point] --> SP[stg_geo__school_point]
    SA --> DY[dim_school_year]
    SA --> DA[dim_authority]
    SB --> DA
    SE --> DS[dim_school]
    SG --> DS
    SP --> DS
    SG --> FE[fact_enrolment]
    G --> FC[fact_capacity]
    GR --> FC
    FC --> FSY[fact_school_year]
    SE --> FSY
    FSY --> AGG[agg_authority_year]
    GR --> AGG
    SA --> AGG
```

### One pipeline run

```mermaid
sequenceDiagram
    participant CLI as abcap run
    participant Log as ops.pipeline_run
    participant Raw as raw.*
    CLI->>Log: insert step "running" (own transaction)
    CLI->>Raw: BEGIN; TRUNCATE; INSERT rows (source_file, source_row, run_id)
    alt success
        CLI->>Raw: COMMIT
        CLI->>Log: status success, rows_in, rows_out, per-file details
    else error
        CLI->>Raw: ROLLBACK (previous load kept)
        CLI->>Log: status failed, root-cause message
    end
    CLI->>Log: verify_raw_counts: source files (openpyxl/JSON) vs table counts
```
