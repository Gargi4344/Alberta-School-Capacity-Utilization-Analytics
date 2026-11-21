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
