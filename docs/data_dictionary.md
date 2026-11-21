# Data dictionary

The mart tables are documented here in Phase 2, when the dbt models exist (and served at `GET /api/v1/dictionary`).

## Rules fixed so far

| Term | Definition | Source |
| --- | --- | --- |
| `school_year` | `YYYY-YY`, taken from the source file name | DECISIONS D2 |
| `authority_code`, `school_code` | 4-digit zero-padded strings | DECISIONS D3 |
| `utilization_rate` (published) | `Adj Total Enrol ÷ Net Capacity`, as given in the capacity file (2023-24); stored as a ratio (0.85 = 85%) | Capacity XLSX `Utiliz. %` |
| `utilization_rate` (school, multi-facility) | `Σ adj_total_enrolment ÷ Σ net_capacity` across the school's facilities | source_mapping.md §3 |
| `utilization_rate` (estimated) | `headcount total ÷ 2023-24 net_capacity`, flagged `is_estimated` | DECISIONS D6 |
| Utilization threshold | 85% by default (`UTILIZATION_THRESHOLD_PCT`); 100% or more is "over capacity" | Spec |

## raw schema (Phase 1)

Loaded by `abcap run`, fully replaced on every run. All raw tables also have the lineage columns `source_file`, `run_id` (the pipeline run that loaded the row) and `loaded_at`.

### `raw.enrolment_school`: one row per school per school year

| Column | Type | Description |
| --- | --- | --- |
| `id` | bigint | Surrogate key |
| `school_year` | varchar(7) | `2016-17` … `2025-26` |
| `authority_category` | varchar | Public, Separate, Francophone, Charter, Private or Provincial, as published |
| `authority_code` | char(4) | School authority code |
| `authority_name` | varchar | Authority name as published that year (names change, codes don't) |
| `school_code` | char(4) | Alberta Education school code |
| `school_name` | varchar | School name as published that year |
| `ungraded`, `ecs`, `grade_1` … `grade_12` | integer | Headcount by grade. Blank in the source means 0. `ungraded` exists from 2025-26 (0 before) |
| `total` | integer | Total headcount (equals the sum of the grade columns in every file) |
| `source_row` | integer | Excel row number in `source_file` |

### `raw.enrolment_authority`: one row per authority per school year

The same columns as `raw.enrolment_school`, without `school_code` and `school_name`. Totals equal the school file summed by authority in every year.

### `raw.capacity`: one row per school × facility (2023-24)

| Column | Type | Description |
| --- | --- | --- |
| `school_year` | varchar(7) | From the file name (`2023-24`) |
| `authority_name`, `school_name` | varchar | As published. **No codes in the source**; joined by name in Phase 2 |
| `facility_name`, `facility_location` | varchar | Facility and community (no coordinates) |
| `net_capacity` | integer | Ministry net capacity of the facility |
| `adj_total_enrolment` | double | Adjusted enrolment (weighted, can be fractional); not the headcount |
| `utilization_rate` | double | Published ratio (0.85 = 85%) |
| `source_row` | integer | Excel row number (the header is on row 3) |

### `raw.authority_boundary`: one row per authority polygon

| Column | Type | Description |
| --- | --- | --- |
| `authority_code`, `authority_name` | varchar | From the layer's `Code` and `Name`. Features without a code are dropped |
| `layer` | varchar | `public` or `separate` (the two layers overlap) |
| `boundary_year` | integer | 2025 |
| `was_invalid` | boolean | True when the published polygon was invalid and was repaired |
| `geom` | geometry(MultiPolygon, 4326) | WGS 84; GiST index |
| `source_feature` | integer | Feature index in the GeoJSON |

### `raw.school_point`: one row per Edmonton Public school (optional)

| Column | Type | Description |
| --- | --- | --- |
| `school_code` | char(4) | From `abed_school_number_t`; blank numbers are dropped |
| `school_name`, `grades`, `school_type`, `address` | varchar | As published by EPSB |
| `geom` | geometry(Point, 4326) | GiST index |

## ops schema

### `ops.pipeline_run`: one row per step per run

| Column | Type | Description |
| --- | --- | --- |
| `run_id` | uuid | Shared by every step of one `abcap run` |
| `step` | varchar | `load_enrolment`, `load_capacity`, `load_boundaries`, `load_school_points`, `verify_raw_counts` (later: dbt, quality, forecast) |
| `source` | varchar | `raw` (full download) or `sample` |
| `started_at`, `finished_at` | timestamptz | `finished_at` is null while running |
| `rows_in`, `rows_out` | integer | Rows read from the source and rows in the table afterwards |
| `status` | varchar | `running`, `success` or `failed` |
| `message` | text | Summary, or the root cause of a failure |
| `details` | jsonb | Per-file row counts and notes (for example `invalid_geometries_repaired`) |
