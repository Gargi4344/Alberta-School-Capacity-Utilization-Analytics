# Decisions

Short records of choices that are not obvious from the code. Newest last.

## D1. Resolve CKAN files through the API, not hard-coded URLs (Phase 0)

`make data` calls open.alberta.ca's `package_show` and downloads every XLSX resource. A new school year is picked up without a code change, and `data/raw/manifest.json` records the URL, size and SHA-256 of each file, so any run can be checked later.

## D2. School year comes from the file name (Phase 0)

Only the 2022-23 and 2023-24 files have a school-year column. The file name (`…-2016-2017.xlsx`) is present and consistent for all 21 workbooks, so it is the single source of `school_year`, stored as `YYYY-YY`.

## D3. Codes are 4-digit strings (Phase 0)

School and authority codes appear as `'0052'`, `52` or `52.0` depending on the year. They are normalized to zero-padded 4-character strings, which matches the boundary layers' `Code` field. Names change over time (78 authorities and 220 schools were renamed), so codes are the only join keys, and dimensions carry the latest name.

## D4. Capacity joins by exact normalized name, no fuzzy matching (Phase 0)

The capacity file has no codes. Exact matching on normalized names links 1,597 of 1,602 rows. The best fuzzy candidates for the other 5 are wrong (Saskatchewan-side Lloydminster schools, and a school no longer in enrolment). A wrong link would corrupt utilization silently, while a missing link is visible in the data quality report. Confirmed manual links go in a committed crosswalk CSV.

## D5. `authority_type` adds `provincial` (Phase 0)

The spec lists public, separate, francophone, charter and private. The data also has a **Provincial** category (5 authorities, for example Northern Lakes College). Dropping it would make school totals stop reconciling with the authority files, so the accepted values include `provincial`.

## D6. Utilization for years without published capacity is estimated and labelled (Phase 0)

Capacity is published for 2023-24 only. For other years, utilization is estimated as headcount ÷ 2023-24 net capacity and flagged `is_estimated = true`. The published 2023-24 value uses adjusted enrolment and stays as given (spec rule: use the source value when provided). The UI never shows an estimated value without the label.

## D7. Map covers public and separate authorities as two layers (Phase 0)

Only public (42) and separate (17) authorities have published polygons, and their boundaries overlap. The map has a public/separate layer switch. Other categories are listed beside the map with a note explaining why they aren't drawn.

## D8. Frontend service behind a Compose profile until Phase 6 (Phase 0)

`docker compose up` must work from Phase 0, before a Next.js app exists, so the `frontend` service sits behind the `frontend` profile. Phase 6 removes the profile.

## D9. Python 3.14, PostgreSQL 18 + PostGIS 3.7 (Phase 0)

These are the latest stable versions as of 2026-11-21, following the spec's "latest stable" rule. The PostgreSQL 18 image keeps its data under `/var/lib/postgresql/18/`, so the volume mounts at `/var/lib/postgresql`.

## D10. Raw keeps the source's wide layout, plus lineage (Phase 1)

`raw.*` tables mirror the files: one column per grade, names and categories as published. The only changes are the ones needed to stack the years (canonical column names, 4-digit codes, blank → 0). Every row records `source_file`, its Excel `source_row` (or GeoJSON `source_feature`) and the `run_id`, so any number in the dashboard can be traced to a cell. Reshaping (grades to rows) happens in dbt staging (Phase 2).

## D11. Full refresh in one transaction per step (Phase 1)

Each load step runs `TRUNCATE` + `INSERT` inside one transaction. The data is small (about 28,000 rows, under 30 seconds), so incremental loading would add complexity for no benefit. Re-running gives identical tables, and a failure rolls back to the previous good load (tested). Optional sources still run when their files are missing and empty their table, so two datasets can never mix: the verify step caught exactly that bug during development.

## D12. Row counts are verified independently of the readers (Phase 1)

`verify_raw_counts` counts source rows with openpyxl and plain JSON using the simplest possible rule (rows below the header with a number in `Total` or `Net Capacity`; features with a non-blank code). It never imports `pipeline.readers`, so a reader bug cannot hide by being repeated on both sides. A mismatch fails the run.

## D13. Explicit column types for every insert (Phase 1)

pandas 3 turns UUID objects into text, which PostgreSQL rejects for `uuid` columns. Every insert passes the table's declared SQLAlchemy types to `to_sql` / `to_postgis`, so pandas never guesses a type.

## D14. The run log stores the root cause of failures (Phase 1)

pandas and SQLAlchemy wrap database errors in messages containing the full SQL statement (over 10 KB). `ops.pipeline_run.message` stores the innermost exception's first line instead, for example `DatatypeMismatch: column "run_id" is of type uuid but expression is of type character varying`.

## D15. The sample excludes the EPSB points (Phase 1)

`data/sample/` is committed to a public repo, so it only contains Open Government Licence – Alberta files. The EPSB layer has its own terms; its loader is covered by a unit test with made-up points instead.
