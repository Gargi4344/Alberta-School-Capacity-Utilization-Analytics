# Progress

| Phase | Status | Notes |
| --- | --- | --- |
| 0. Scaffold, Compose, `make data`, source mapping | ✅ Done 2026-11-21 | See below |
| 1. Extract and load raw tables, `ops.pipeline_run` | ✅ Done 2026-11-21 | See below |
| 2. dbt staging and marts | ✅ Done 2026-11-21 | See below |
| 3. Quality checks | Next | |
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

## Phase 2 (2026-11-21)

**Done-when check: `dbt build` passes and the star schema can be queried.** `abcap run` now ends with a logged `dbt_build` step: 75 nodes (1 seed, 9 views, 7 tables, 58 tests): **74 pass, 1 expected warning** (the 5 capacity rows that match no school, the same 5 as the Phase 0 audit). `dbt docs generate` works (`make dbt-docs`).

| Mart | Rows |
| --- | ---: |
| dim_school_year / dim_authority / dim_school | 10 / 373 / 2,545 |
| fact_enrolment (22,815 school-years × 14 grade columns) | 319,410 |
| fact_capacity (1,597 matched rows − 5 extra campus rows) | 1,592 |
| fact_school_year / agg_authority_year | 22,815 / 3,036 |

Checks built into `dbt build`: keys unique and not null, facts → dims relationships, accepted authority types, school totals = authority files every year, grade rows = published totals, computed utilization = printed value (half-up rounding), each facility counted once in authority capacity, capacity groups stay simple, estimate = published in the capacity year.

**Found while building:**

- The capacity file repeats shared and multi-campus numbers. Capacity groups count each facility once (D16). Phase 0's "13 shared facilities" was really 10 (corrected in source_mapping.md).
- A raw headcount estimate would flag 69 fewer schools than the published figures in the same year, putting a jump in every trend. Estimates are now calibrated (D17); schools over 85% run 492 → 572 → 632 for 2022-23 → 2024-25 with no method break.
- 190 ÷ 400 = 0.475 is printed as 0.48 (half-up). The test compares with the source's rounding rather than a tolerance.
- 51 tests pass, including dbt on the sample and a check that the SQL and Python name normalizations agree on every name in the data.

**Headline (2025-26, estimated):** 609 schools at or over 85% and 262 at or over 100%. Calgary Public is at 95.1% and Edmonton Catholic at 100.9%.

**Carried into Phase 3:** the custom quality checks into `ops.dq_result` (negative headcounts, utilization outside 0–250%, capacity without enrolment and the reverse, year-over-year change over 50%, duplicate names), plus surfacing the dbt test results there.

**Local environment notes (Windows):**

- GNU make is not installed on this machine. Either install it (`winget install ezwinports.make`) or run the commands in the Makefile directly (for example `cd backend && uv run abcap download`).
- uv was installed with `pip install --user uv`, so run it as `python -m uv` unless its Scripts folder is on PATH.
