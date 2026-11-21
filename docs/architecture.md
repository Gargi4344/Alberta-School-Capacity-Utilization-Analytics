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

**Status (Phase 1):** built so far: download, extract/load into `raw` (Pandas, GeoPandas), the independent row-count check, `ops.pipeline_run`, Compose (db and backend) and `/api/v1/health`. dbt, quality checks, forecasts and the dashboard follow in Phases 2 to 6.

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
