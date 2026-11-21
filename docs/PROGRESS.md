# Progress

| Phase | Status | Notes |
| --- | --- | --- |
| 0. Scaffold, Compose, `make data`, source mapping | ✅ Done 2026-11-21 | See below |
| 1. Extract and load raw tables, `ops.pipeline_run` | ✅ Done 2026-11-21 | See below |
| 2. dbt staging and marts | Next | |
| 3. Quality checks | — | |
| 4. Forecasts and notebooks | — | |
| 5. FastAPI endpoints | — | `/api/v1/health` exists |
| 6. Next.js app | — | |
| 7. Briefing and exports | — | |
| 8. Playwright, CI, README | — | CI runs lint, unit and database tests, and the pipeline on the sample |

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

**Carried into Phase 1:** build `data/sample/`, and cast every boundary to MultiPolygon. Both done (see Phase 1).

## Phase 1 (2026-11-21)

**Done-when check: raw row counts match the source files.** `abcap run` (full data):

| Step | Rows in | Rows out |
| --- | ---: | ---: |
| load_enrolment (20 files: 22,815 school + 3,036 authority rows) | 25,851 | 25,851 |
| load_capacity | 1,602 | 1,602 |
| load_boundaries (42 public + 17 separate; 4 invalid polygons repaired) | 59 | 59 |
| load_school_points (EPSB) | 224 | 224 |
| verify_raw_counts (24 files, counted independently with openpyxl/JSON) | 27,736 | 27,736 |

- Every step is in `ops.pipeline_run` under one `run_id`; `GET /api/v1/health` reports the last successful run.
- Spot check: Big Valley School (`4601`) has total 82 in 2016-17 (Excel row 6) and 86 in 2025-26 (row 5), the same as the published files.
- Re-running replaces instead of appending (same counts, one `run_id` in raw).
- `data/sample/`: 9 authorities covering all 6 categories, 23 files, 440 KB, 3,340 rows; `abcap run --source sample` passes the same verification. CI runs it with no download.
- 42 tests pass (`REQUIRE_DB=1`), including 7 against PostgreSQL: counts, lineage, geometry validity, re-runs, a failed run that rolls back and is logged as `failed`, and the health check.

**Bugs found and fixed while building:**

- pandas 3 sends UUIDs as text, which PostgreSQL refuses for a `uuid` column. Every insert now passes explicit column types (D13), and the run log stores the root cause instead of 10 KB of SQL (D14).
- The verify step caught stale EPSB rows left over from an earlier full run when the sample (no EPSB file) was loaded. Optional steps now always empty their table (D11).
- Correction to Phase 0: 224 of the 225 EPSB points have a usable school number. *Ellerslie Campus South* has a blank one.

**Carried into Phase 2:** the dbt project. Staging unpivots grades, the capacity name join follows D4, and the marts follow the spec's star schema.

**Local environment notes (Windows):**

- GNU make is not installed on this machine. Either install it (`winget install ezwinports.make`) or run the commands in the Makefile directly (for example `cd backend && uv run abcap download`).
- uv was installed with `pip install --user uv`, so run it as `python -m uv` unless its Scripts folder is on PATH.
