# Source mapping

How the public source files are laid out, how they join, which years they cover, and where the gaps are. Written in Phase 0 after inspecting every downloaded file.

- **Inspected:** 2026-11-21, from the files `make data` downloaded (listed with SHA-256 in `data/raw/manifest.json`).
- **Reproduce:** `make audit` recomputes every number on this page into [`source_audit.json`](source_audit.json), using the same readers the pipeline uses (`backend/pipeline/readers.py`).
- **Licence:** all Alberta Education files are under the Open Government Licence – Alberta. The Edmonton Public Schools layer is optional and comes with its own terms.

## 1. Inventory

| Source | Fetched from | Files | Years | Grain |
| --- | --- | --- | --- | --- |
| Student enrolment by school and grade | CKAN `student-enrolment-by-school-authority-and-grade-level` | 10 XLSX (`*-school-enrolment-data-YYYY-YYYY.xlsx`) | 2016-17 to 2025-26 | school × year, grades as columns |
| Student enrolment by authority and grade | same dataset | 10 XLSX (`*-authority-enrolment-data-YYYY-YYYY.xlsx`) | 2016-17 to 2025-26 | authority × year, grades as columns |
| School jurisdiction schools with total capacity | CKAN `list-of-albertas-school-jurisdiction-schools-with-their-total-capacity-for-the-school-year` | 1 XLSX (`educ-school-capacity-2023-2024-school-year.xlsx`) | **2023-24 only** | school × facility |
| Public school authority boundaries | ArcGIS `edu_public_schl_auth_bound_2025_group_public/MapServer/3` | GeoJSON, EPSG:4326 | 2025 | authority polygon |
| Separate school authority boundaries | ArcGIS `edu_separate_schl_auth_bound_2025_group_public/MapServer/3` | GeoJSON, EPSG:4326 | 2025 | authority polygon |
| Edmonton Public school points (optional) | ArcGIS `azimuth.epsb.ca/.../Schools__2025/FeatureServer/62` | GeoJSON | 2025-26 | school point |

`make data` resolves the CKAN files through the open.alberta.ca API (`package_show`) instead of hard-coding URLs, so a newly published year is picked up automatically. ArcGIS layers are queried with `where=1=1&outFields=*&outSR=4326&f=geojson`, with paging.

## 2. Enrolment files

### Real column names, and how they drift

Every file has one sheet (`Alberta School Enrolment Data`) with the header on row 1.

| Canonical column | Header in the source | Notes |
| --- | --- | --- |
| `school_year` | taken from the **file name** | A `School Year` / `School Year Name` column (`2022/2023`) exists only in the 2022-23 and 2023-24 files |
| `authority_category` | `School Authority Category`; `SchoolAuthorityCategory` (2025-26 school file) | Public, Separate, Francophone, Charter, Private, Provincial |
| `authority_name` | `School Authority Name` | Some values have trailing spaces (for example `Northern Lakes College ` in 2022-23) |
| `authority_code` | `School Authority Code` | Text with leading zeros (`'0052'`) to 2024-25; an integer (`52`) in 2025-26. Normalized to a 4-digit string |
| `school_name` | `School Name`; `School Name\n` (2016-17); `SchoolName` (2025-26) | School files only |
| `school_code` | `School Code`; `SchoolCode` (2025-26) | Text or integer, as above. Normalized to a 4-digit string |
| `ungraded` | `Ungraded` | **New in 2025-26.** Set to 0 for earlier years |
| `ecs` | `ECS` | Early Childhood Services (kindergarten) |
| `grade_1` … `grade_12` | `Grade 1` … `Grade 12` | |
| `total` | `Total` | |

Other quirks the reader handles:

- **Empty unnamed columns:** 2016-17 has one between `Grade 1` and `Grade 2`, and 2017-18 to 2019-20 have one after `School Code`. They hold no values and are dropped.
- **Footnote row:** every file ends with a row that starts `*First Nation school level enrolment statistics have been removed from this report…`. It is dropped. **First Nation schools are not in these files**, so they cannot appear in the platform (see Gaps).
- **Blanks mean zero:** files up to 2024-25 leave a grade cell blank when there are no students; 2025-26 writes `0`. No suppression markers (`*`, `<10`), negative values or fractions occur in any file.

### Checks run on all 20 files

| School year | Schools | Authorities | Provincial total | School files vs authority files |
| --- | ---: | ---: | ---: | --- |
| 2016-17 | 2,225 | 294 | 694,209 | match exactly |
| 2017-18 | 2,256 | 294 | 708,968 | match exactly |
| 2018-19 | 2,276 | 299 | 719,450 | match exactly |
| 2019-20 | 2,274 | 292 | 731,345 | match exactly |
| 2020-21 | 2,262 | 294 | 722,302 | match exactly |
| 2021-22 | 2,275 | 303 | 733,116 | match exactly |
| 2022-23 | 2,289 | 312 | 756,729 | match exactly |
| 2023-24 | 2,303 | 313 | 788,019 | match exactly |
| 2024-25 | 2,318 | 316 | 811,847 | match exactly |
| 2025-26 | 2,337 | 319 | 820,895 | match exactly |

- In every year, the school file summed by `authority_code` equals the authority file for **every** authority. Phase 3 keeps this as a data quality check.
- Each row's `total` equals the sum of its grade columns in every file.
- `school_code` is unique within each year.

### Code stability over time

| Fact | Count |
| --- | ---: |
| Distinct school codes, 2016-17 to 2025-26 | 2,545 |
| School codes present in all 10 years | 2,015 |
| School codes with at least 6 years (eligible for school-level forecasts) | 2,232 |
| School codes whose name changed at least once | 220 |
| School codes that moved to a different authority | 6 |
| Distinct authority codes | 373 |
| Authority codes whose name changed at least once | 78 |

The name changes are mostly the 2019 renaming under the *Education Act*, for example `0019` *Red Deer Catholic Regional Division No. 39* (2016-17 to 2018-19) becoming *The Red Deer Catholic Separate School Division* (2019-20 on). **Codes are the join keys, and `dim_school` / `dim_authority` take the latest name.**

## 3. Capacity file

### Real column names

The sheet is `ACU 2023-24F`. Rows 1 and 2 are blank, so the header is on **row 3** (the reader finds it by looking for `Net Capacity`).

| Source header | Canonical column | Notes |
| --- | --- | --- |
| `School Authority Name` | `authority_name` | |
| `School Name` | `school_name` | |
| `Facility Name` | `facility_name` | Upper case, for example `AURORA ELEMENTARY SCHOOL/AURORA MIDDLE SCHOOL` |
| `Facility Location` | `facility_location` | Community name (for example `EDMONTON`), not coordinates |
| `Net Capacity` | `net_capacity` | Integer, never 0 |
| `Adj Total Enrol` | `adj_total_enrolment` | Adjusted enrolment, with halves (for example `163.5`). It is the ministry's weighted count, not the headcount in the enrolment files |
| `Utiliz. %` | `utilization_rate` | A **ratio** (0.85 means 85%). It equals `Adj Total Enrol ÷ Net Capacity` rounded to 2 decimals in all 1,602 rows. Range 0.04 to 2.25 |

1,602 data rows cover 82 authorities, 1,542 school names and 1,540 facility names. 4 schools span more than one facility, and 10 facilities are shared by more than one school (20 schools). *(Corrected in Phase 2: Phase 0 grouped by facility name only and counted 13. Black Gold's two "Robina Baker" rows have different capacities and are two buildings, and St. Augustine is one school with two same-named buildings.)* The source repeats a shared facility's numbers on each school's row; see DECISIONS D16 for how they are counted once.

### How capacity joins to enrolment

**The capacity file has no school codes and no authority codes**, so it can only join by name. Joined against the 2023-24 enrolment file:

1. **Authority:** the normalized name (ASCII, lower case, punctuation removed, `St.` → `saint`) matches **82 of 82** authorities exactly: all 42 public, 17 separate and 4 francophone authorities, plus 19 of the 26 charter authorities. Private and provincial authorities are not in the capacity file.
2. **School, within its authority:** the normalized school name matches exactly one enrolment school for **1,597 of 1,602 rows (99.7%)**. The 5 that don't match:

| Authority | School in capacity file | Why it doesn't match |
| --- | --- | --- |
| Lloydminster Public School Division | E S Laird | Saskatchewan-side Lloydminster school; not in Alberta enrolment |
| Lloydminster Public School Division | Jack Kemp School | Same |
| Lloydminster Public School Division | Winston Churchill | Same |
| Lloydminster Roman Catholic Separate School Division | Father Gorman Elementary School | Same |
| The Greater St. Albert Roman Catholic Separate School Division | Ecole Marie Poburan | Last appears in enrolment in 2022-23 |

**Rule for Phase 1:** match on the exact normalized name only. Fuzzy matching was tested (rapidfuzz `token_sort_ratio`); for these 5 rows the best candidates score 40 to 75 and would all be wrong links. Unmatched rows stay in `raw`, and the "capacity without enrolment" check reports them. Any confirmed manual link goes in a small committed crosswalk file, never into code.

**Grain:** `mart.fact_capacity` is school × year. Where a school spans several facilities, capacity and adjusted enrolment are summed and utilization is recalculated as `sum(adj_total_enrolment) ÷ sum(net_capacity)`. For single-facility schools this equals the published value. The formula goes in `docs/data_dictionary.md`. Facilities shared by several schools keep the published per-school rows.

**Coverage:** 1,983 schools in the 2023-24 enrolment file belong to the 82 matched authorities. **391 of them have no capacity row.** They are mostly programs without a capacity-rated facility of their own: 172 colony schools, 44 outreach schools, 29 online, virtual, distance or home-education programs, plus alternate, career and group-care programs. Together they enrol **39,028 of 732,378 students (5.3%)** in those authorities. They get enrolment but no utilization, and authority utilization totals use only schools that have capacity (documented in the data dictionary).

## 4. Boundaries

| Layer | Features | Features with no `Code` | Distinct codes | Codes found in 2025-26 enrolment |
| --- | ---: | ---: | ---: | ---: |
| Public authorities 2025 | 43 | 1 | 42 | 42 |
| Separate authorities 2025 | 23 | 6 | 17 | 17 |

- Fields: `Name`, `Code`, `OBJECTID`, plus the geometry (Polygon and MultiPolygon mixed; the loader casts everything to MultiPolygon). `Code` normalizes to the same 4-digit `authority_code` as the enrolment files.
- Features with no code are areas outside any authority. They are dropped.
- **Coverage by category (2025-26):**

| Category | Authorities | With a polygon |
| --- | ---: | ---: |
| Public | 42 | 42 |
| Separate | 17 | 17 |
| Francophone | 4 | 0 |
| Charter | 26 | 0 |
| Private | 225 | 0 |
| Provincial | 5 | 0 |

**Map consequence:** the choropleth works at **authority level for public and separate authorities only**, shown as two switchable layers because public and separate boundaries overlap. Francophone, charter, private and provincial authorities have no published boundary. The map page says so and lists them in a table next to the map. There are no province-wide school coordinates in these sources, so the provincial map stays at authority level.

### Edmonton Public school points (optional)

225 points with `abed_school_number_t` (the Alberta Education school number). 224 carry a usable number. The 225th, *Ellerslie Campus South*, has a blank number (`' '`): it is a campus, not a school, and is dropped. The 224 numbers match **224 of 224** Edmonton Public (`3020`) schools in 2025-26 enrolment, so the optional Edmonton school-level layer joins on `school_code` directly. *(Corrected in Phase 1: the Phase 0 check counted the blank as a number.)*

The layer has its own terms of use, so it is **not** copied into the committed `data/sample/`.

### Geometry validity

4 polygons are invalid as published (1 public, 3 separate). The loader repairs them with Shapely's `make_valid` instead of dropping them, keeps only the polygon parts, and sets `raw.authority_boundary.was_invalid = true` for traceability.

## 5. Year coverage

| Data | 2016-17 … 2022-23 | 2023-24 | 2024-25 | 2025-26 |
| --- | --- | --- | --- | --- |
| Enrolment, school and authority | ✓ | ✓ | ✓ | ✓ |
| Capacity and utilization | — | ✓ | — | — |
| Boundaries | — | — | — | 2025 layers |

## 6. Gaps and what the platform does about them

1. **Capacity exists for one year (2023-24).** The spec's `fact_capacity` is school × year, but open.alberta.ca currently publishes only 2023-24. Consequences:
   - Utilization **as published** exists for 2023-24 only.
   - For other years, the platform shows **estimated utilization**: that year's enrolment headcount ÷ 2023-24 net capacity. It is labelled "estimated, capacity held at 2023-24" everywhere it appears. This is the same assumption the forecast already makes, extended backwards. Headcount is not adjusted enrolment, so estimated and published values are not strictly comparable. The data dictionary states the formula, and the UI shows the 2023-24 published value next to it.
   - The loader accepts more capacity files as they are published, because the downloader picks them up and the file name sets `school_year`.
2. **Capacity uses adjusted enrolment, not headcount.** The published utilization uses the ministry's adjusted enrolment, not the headcount in the enrolment files, and the two differ. Both are stored and never mixed in one formula without a label.
3. **No codes in the capacity file.** It joins by name (section 3), with 5 rows left unmatched and reported.
4. **First Nation schools are excluded** from the enrolment files by the publisher. This is a limitation in the README.
5. **Boundaries are 2025 only.** Historical authority maps use the 2025 polygons, which is fine because authority codes are stable.
6. **Category list:** the spec lists public, separate, francophone, charter and private. The data also has **Provincial** (5 authorities, for example Northern Lakes College). `authority_type` accepts `provincial` as well; see DECISIONS.md.
7. **No "preliminary" flag in the files.** `dim_school_year.is_preliminary` is driven by a setting (default: the latest year, 2025-26), because the files don't say which years are preliminary. Check the ministry's notes on the dataset page before relying on it.
