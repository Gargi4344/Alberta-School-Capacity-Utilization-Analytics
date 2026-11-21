# Data dictionary

Every table the API reads. dbt also publishes these descriptions and tests as browsable docs (`make dbt-docs`), and `GET /api/v1/dictionary` will serve them in Phase 5.

## Definitions

| Term | Definition |
| --- | --- |
| `school_year` | `YYYY-YY`, taken from the source file name (D2) |
| `authority_code`, `school_code` | 4-digit zero-padded strings (D3) |
| Capacity group | Schools sharing a facility, or one school with all its facilities (D16) |
| Capacity | Net capacity of the capacity group: sum over its distinct facilities |
| Adjusted enrolment | The ministry's weighted enrolment from the capacity file (not headcount) |
| Utilization, published | Group adjusted enrolment ÷ group capacity, in years with published capacity (2023-24). For a school with one capacity row it equals the printed `Utiliz. %` (tested) |
| Adjustment factor | Group adjusted enrolment ÷ group headcount in the capacity year (D17) |
| Utilization, estimated | Group headcount that year × adjustment factor ÷ latest published capacity (capacity held flat). Equals the published value in 2023-24 (tested) |
| `utilization_rate` | Published when available, else estimated; `utilization_basis` says which |
| Over threshold | `utilization_rate >= 0.85` (`UTILIZATION_THRESHOLD_PCT`, default 85) |
| Over capacity | `utilization_rate >= 1.00` (`OVER_CAPACITY_PCT`, default 100) |

All utilization values are stored as ratios (0.85 = 85%).

## mart schema (Phase 2): the star schema

| Table | Grain | Rows (full data) |
| --- | --- | ---: |
| `mart.dim_school_year` | school year | 10 |
| `mart.dim_authority` | authority ever reported | 373 |
| `mart.dim_school` | school ever reported | 2,545 |
| `mart.fact_enrolment` | school × year × grade | 319,410 |
| `mart.fact_capacity` | school × capacity year | 1,592 |
| `mart.fact_school_year` | school × year | 22,815 |
| `mart.agg_authority_year` | authority × year | 3,036 |

### `mart.dim_school_year`

| Column | Description |
| --- | --- |
| `school_year` (PK) | `2016-17` … `2025-26` |
| `start_year` | 2016 … 2025 |
| `is_preliminary` | dbt var `preliminary_school_years`; default the latest year |
| `has_published_capacity` | True for 2023-24 |

### `mart.dim_authority`

| Column | Description |
| --- | --- |
| `authority_code` (PK) | Authority code |
| `authority_name` | Name in the latest year reported |
| `authority_type` | public, separate, francophone, charter, private, provincial (D5) |
| `first_school_year`, `last_school_year`, `years_reported`, `is_active` | Reporting span; active = reported in the latest year |
| `boundary_layer` | public or separate; null when no boundary is published |
| `geometry_was_repaired` | The published polygon was invalid and was repaired |
| `geom` | MultiPolygon, EPSG:4326, GiST index. 59 of 373 authorities have one |

### `mart.dim_school`

| Column | Description |
| --- | --- |
| `school_code` (PK) | School code |
| `school_name`, `authority_code` | From the latest year reported (FK to `dim_authority`) |
| `grades_offered` | Grades with students in the latest year, for example `ECS–6`, `10–12`, `Ungraded` |
| `first_school_year`, `last_school_year`, `years_reported`, `is_open` | Reporting span; open = reported in the latest year |
| `geom` | Point, EPSG:4326. Edmonton Public schools only (224) |

### `mart.fact_enrolment`

`school_code`, `school_year`, `grade` (Ungraded, ECS, 1–12), `grade_order` (-1 Ungraded, 0 ECS, 1–12), `authority_code` (the school's authority that year), `headcount`. Zeros are kept. Sums reconcile with the published school totals and with the authority files (tested).

### `mart.fact_capacity`

| Column | Description |
| --- | --- |
| `school_code`, `school_year` | Unique together |
| `authority_code`, `capacity_group_id` | |
| `capacity`, `adjusted_enrolment`, `utilization_rate` | The capacity group's values |
| `published_utilization_rate` | The printed 2-decimal value, for schools with one capacity row |
| `facility_count`, `schools_in_group`, `shares_facility`, `has_multiple_facilities` | Group structure |

### `mart.fact_school_year`

| Column | Description |
| --- | --- |
| `school_code`, `school_year`, `start_year`, `authority_code` | Unique per school and year |
| `total_enrolment` | Headcount |
| `capacity_group_id`, `capacity`, `capacity_school_year` | Latest published capacity of the school's group (null if none) |
| `capacity_group_enrolment` | Headcount of all schools in the group that year |
| `adjustment_factor`, `capacity_group_adjusted_enrolment` | Calibration (D17) |
| `utilization_estimated`, `utilization_published`, `utilization_rate`, `utilization_basis` | See Definitions |
| `is_over_threshold`, `is_over_capacity` | Flags at 85% and 100% |

### `mart.agg_authority_year`

| Column | Description |
| --- | --- |
| `authority_code`, `school_year` | Unique together |
| `total_enrolment` | Official authority total (all schools) |
| `school_count`, `schools_with_capacity` | |
| `total_capacity` | Sum over the authority's capacity groups with enrolment that year (each facility once) |
| `enrolment_in_capacity_schools` | Headcount of those groups |
| `utilization_estimated`, `utilization_published`, `utilization_rate`, `utilization_basis` | Group-weighted, see Definitions |
| `schools_over_85`, `schools_over_100` | Schools at or above the thresholds |

## staging schema

dbt views that clean and reshape `raw` (`stg_*`), the capacity matching and grouping (`int_capacity__*`), and the `capacity_school_crosswalk` seed. They are internal; the API reads only `mart`.

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
