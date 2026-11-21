-- Runs once, when the database volume is first created (docker-entrypoint-initdb.d).
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS raw;      -- source files loaded as-is (Phase 1)
CREATE SCHEMA IF NOT EXISTS staging;  -- dbt staging models (Phase 2)
CREATE SCHEMA IF NOT EXISTS mart;     -- dbt star schema (Phase 2)
CREATE SCHEMA IF NOT EXISTS ops;      -- pipeline runs and data quality results (Phase 1+)
