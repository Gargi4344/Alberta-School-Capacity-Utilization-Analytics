# Progress

| Phase | Status | Notes |
| --- | --- | --- |
| 0. Scaffold, Compose, `make data`, source mapping | ✅ Done 2026-11-21 | See below |
| 1. Extract and load raw tables, `ops.pipeline_run` | Next | |
| 2. dbt staging and marts | — | |
| 3. Quality checks | — | |
| 4. Forecasts and notebooks | — | |
| 5. FastAPI endpoints | — | `/api/v1/health` exists |
| 6. Next.js app | — | |
| 7. Briefing and exports | — | |
| 8. Playwright, CI, README | — | CI workflow exists (backend lint and tests, Compose and PostGIS) |

## Phase 0 (2026-11-21)

**Done-when check:**

- `docker compose up -d --wait` → db and backend healthy. PostgreSQL 18.7 and PostGIS 3.7.0, with schemas `raw`, `staging`, `mart` and `ops`. `GET /api/v1/health` returns `{"status":"ok","database":"up","postgis_version":"3.7.0"}`, and `/docs` returns 200.
- `make data` → 24 files: 20 enrolment workbooks (2016-17 to 2025-26, school and authority), 1 capacity workbook (2023-24), 3 GeoJSON layers (43 public and 23 separate authority features, 225 EPSB school points). 9.3 MB in total.
- `docs/source_mapping.md` is written from the real files; `make audit` reproduces its numbers.
- `ruff check`, `ruff format --check` and `pytest` (31 tests) pass locally.

**Found in Phase 0 that changes the plan:**

- Capacity is published for **one year only** (2023-24) and has **no codes**. It joins by name: 1,597 of 1,602 rows match (DECISIONS D4, D6).
- Boundaries exist only for public and separate authorities (D7).
- There is a sixth category, `Provincial` (D5).

**Carried into Phase 1:**

- Build `data/sample/` (a small real subset: a few authorities × all years, plus their capacity rows and polygons) so CI can run the pipeline offline.
- The loader casts every boundary to MultiPolygon and drops features with no code.

**Local environment notes (Windows):**

- GNU make is not installed on this machine. Either install it (`winget install ezwinports.make`) or run the commands in the Makefile directly (for example `cd backend && uv run abcap download`).
- uv was installed with `pip install --user uv`, so run it as `python -m uv` unless its Scripts folder is on PATH.
