# SPEC: Project 1: Alberta School Capacity & Utilization Planning Platform

This file is the full specification for the `Alberta-School-Capacity-Utilization-Analytics` repo. Read all of it before writing code. Follow the shared standards for everything, plus the project section.

## Shared stack and standards

All three projects use the same stack: **Python** for data and the API, **TypeScript** for the web app, **SQL** in PostgreSQL. These are the most-used languages in data jobs, and Python, Pandas and SQL are named in the posting. Use the latest stable version of every tool.

| Layer | Tool | Why |
| --- | --- | --- |
| Frontend | Next.js (App Router) + TypeScript + React | The most widely used React framework |
| UI | Tailwind CSS + shadcn/ui + lucide-react icons | Modern, clean, accessible components |
| Charts and tables | Recharts (via shadcn charts) + TanStack Table + TanStack Query | Interactive dashboards, sortable and filterable tables, data caching |
| Maps | MapLibre GL (react-map-gl) | Free, open-source vector maps |
| Forms | react-hook-form + Zod | Typed client-side validation |
| Backend API | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic | The leading Python API stack, with typed schemas and migrations |
| Database | PostgreSQL + PostGIS + pgvector | Warehouse, geospatial and vector search in one database |
| Data processing | Pandas, GeoPandas, openpyxl | Named in the posting; reads the Excel open data |
| Python tooling | uv, ruff, pytest, Typer (CLI) | Fast, current Python project tooling |
| Frontend tooling | pnpm, ESLint, Prettier, Vitest, Playwright | Unit and end-to-end tests |
| Packaging | Docker + Docker Compose | One command to run everything |
| CI | GitHub Actions | Lint, test and build on every push |

**Repo layout (every project):**

```text
<repo>/
  SPEC.md
  README.md
  docker-compose.yml      (db, backend, frontend)
  Makefile                (setup, pipeline, dev, test, lint)
  .env.example
  .github/workflows/ci.yml
  backend/
    pyproject.toml        (managed with uv)
    app/
      main.py
      api/v1/             (one router per resource)
      core/               (config, logging, security)
      db/                 (session, models, alembic migrations)
      schemas/            (Pydantic request/response models)
      services/           (business logic, no HTTP code)
    pipeline/             (extract, load, transform, quality; Typer CLI)
    tests/
  frontend/
    app/                  (Next.js routes)
    components/           (ui/ from shadcn, plus feature components)
    lib/                  (API client, types, utils)
    tests/                (Vitest unit, Playwright e2e)
  data/
    raw/                  (gitignored; filled by the download script)
    sample/               (small committed sample so CI and demos run)
  docs/
    source_mapping.md  DECISIONS.md  PROGRESS.md  data_dictionary.md  architecture.md
  notebooks/              (Jupyter notebooks that explain the analysis)
```

**Engineering rules:**

- **API:** REST under `/api/v1`, typed Pydantic responses, pagination on lists (`page`, `page_size`), one error format `{"error": {"code", "message", "details"}}`. FastAPI's OpenAPI docs must work at `/docs`.
- **Layers:** routers only handle HTTP; logic lives in `services/`; database access goes through SQLAlchemy models. No SQL strings built from user input.
- **Config:** everything from environment variables (`pydantic-settings`), documented in `.env.example`. No secrets in the repo.
- **Data:** never commit large raw files. `make data` downloads them. `data/sample/` holds a small real subset so tests and CI run offline.
- **Testing:** pytest for services, pipeline and API (target: every endpoint has at least one test); Vitest for frontend utilities; one Playwright test for the main user journey.
- **Quality gates:** ruff and ESLint pass, TypeScript `strict` on, CI green before a phase is called done.
- **Logging:** structured JSON logs in the backend; every pipeline run gets a `run_id` stored in the database.

**UI design rules (the "good-looking" part):**

- A calm, professional analytics look: neutral background, white cards with soft borders, **one** accent colour, generous spacing, and a single font (Inter or Geist).
- Layout: left sidebar navigation, top bar with page title and filters, content in a responsive card grid. Works from 375 px phones to wide screens.
- Every page has loading skeletons, an empty state with a helpful message, and a friendly error state.
- Dark mode toggle.
- Accessibility: WCAG 2.1 AA contrast, full keyboard navigation, labelled form fields, charts with text summaries or a data table view.
- Numbers formatted for Canada (`en-CA`): thousands separators, CAD currency, percentages to one decimal place.
- Canadian spelling in the interface: enrolment, catalogue, colour.
- Every page shows where its data comes from and the as-of date in a small footer line.

**Every README must have:** the problem in 2 sentences, screenshots or a GIF, a Mermaid architecture diagram, the tech stack, setup in 5 commands or fewer, data sources and licence (Open Government Licence – Alberta), sample-data labels, limitations, and "What I learned".

## Project 1: Alberta School Capacity & Utilization Planning Platform

**Repo name:** `Alberta-School-Capacity-Utilization-Analytics`

### Goal

Build a web platform that answers a capital planner's core question: **which Alberta school authorities and schools are running out of space, and where is enrolment heading?** It integrates 10 years of public enrolment, capacity and boundary data into a PostgreSQL warehouse, checks its quality, forecasts enrolment 3 years ahead, and serves it through a self-service dashboard with maps and auto-generated briefing notes.

**Users:** a ministry capital planning analyst and their manager.

**Job requirements it proves:** databases, data warehouse, data models, ETL; Python and Pandas; dashboards, forecasts, self-service reporting; governance, validation and reproducibility; briefings; enrolment, geospatial, capacity and utilization data.

### Extra tools for this project

- **dbt Core (dbt-postgres):** SQL transformations from raw to star schema, with tests and generated docs.
- **statsmodels:** enrolment forecasting.
- **python-docx:** briefing note export to Word.

### Data sources (public, Open Government Licence – Alberta)

1. **Student enrolment by school, authority and grade level:** one Excel file per school year, 2016/17 to 2025/26, from open.alberta.ca (see Sources).
2. **School jurisdiction schools with total capacity:** capacity and utilization rate per school facility, from open.alberta.ca.
3. **Alberta School Authority Boundaries:** polygons from the ArcGIS REST service on geospatial.alberta.ca. Query each layer with `/query?where=1=1&outFields=*&outSR=4326&f=geojson`.
4. **Optional, Edmonton Public school points:** ArcGIS FeatureServer, for a school-level map of Edmonton.

Phase 0 must inspect every file and write `docs/source_mapping.md`: the real column names, how school codes and authority codes join across files, which years each file covers, and any gaps. If a source has no coordinates for schools, the map works at authority level and says so.

### Architecture

```text
make data      -> download Excel + GeoJSON into data/raw/
make pipeline  -> extract/load (Python, Pandas, GeoPandas) -> raw schema in PostgreSQL
               -> dbt build: staging -> marts (star schema) + dbt tests
               -> quality: dbt test results + custom checks -> dq tables
               -> forecast (statsmodels) -> mart.fact_forecast
               -> each step logs to ops.pipeline_run
FastAPI (/api/v1) reads marts -> Next.js dashboard (charts, map, tables, briefing, exports)
```

### Data model (schemas: raw, staging, mart, ops)

| Table | Grain | Key columns |
| --- | --- | --- |
| `mart.dim_authority` | one row per school authority | authority_code (PK), authority_name, authority_type (public, separate, francophone, charter, private), geom (PostGIS MultiPolygon, nullable) |
| `mart.dim_school` | one row per school | school_code (PK), school_name, authority_code (FK), grades_offered, geom (Point, nullable) |
| `mart.dim_school_year` | one row per school year | school_year (PK, e.g. 2025-26), start_year, is_preliminary |
| `mart.fact_enrolment` | school × year × grade | school_code, school_year, grade, headcount |
| `mart.fact_capacity` | school × year | school_code, school_year, capacity, adjusted_enrolment, utilization_rate (all as given in the source) |
| `mart.fact_forecast` | authority or school × target year | level, code, target_year, predicted_enrolment, lower_80, upper_80, model_name, run_id |
| `mart.agg_authority_year` | authority × year | total_enrolment, total_capacity, utilization_rate, schools_over_85, schools_over_100 |
| `ops.pipeline_run` | one row per run | run_id, step, started_at, finished_at, rows_in, rows_out, status, message |
| `ops.dq_result` | check × run | run_id, check_name, table_name, severity, status, failed_rows, sample_failures (jsonb) |

Rules: utilization comes from the source when it is provided; when calculated, the formula goes in `docs/data_dictionary.md`. The 85% threshold is configurable (default 85, the province's optimal rate); 100% or more is "over capacity".

### Data quality checks

- dbt tests: unique and not_null keys, relationships (school to authority, facts to dims), accepted values for authority_type.
- Custom checks: negative headcounts; utilization outside 0–250%; schools in capacity data but not in enrolment data (and the reverse); year-over-year enrolment change over 50% (warning); duplicate school names under different codes (warning).
- Every check writes to `ops.dq_result`. Errors stop the pipeline; warnings do not.

### Forecasting

- Per authority, plus per school for schools with at least 6 years of data: Holt's linear trend (statsmodels ExponentialSmoothing) on total enrolment, horizon 3 school years, with an 80% interval.
- Backtest: train on all years except the last 2, report MAPE per authority. Show it in the UI so users see how reliable the forecast is.
- Projected utilization = forecast enrolment ÷ latest capacity (assumes capacity stays flat; say so in the UI).

### API endpoints (FastAPI, `/api/v1`)

| Method and path | Returns |
| --- | --- |
| `GET /metrics/summary?year=` | KPI cards: total enrolment, schools, average utilization, schools over 85% and over 100%, change vs last year |
| `GET /authorities?year=&type=` | Authority list with enrolment, capacity, utilization |
| `GET /authorities/{code}` | Authority detail, 10-year trend, forecast, schools |
| `GET /schools?search=&authority=&min_util=&max_util=&year=&page=` | Paginated, filterable school list |
| `GET /schools/{code}` | School detail: enrolment by grade over time, capacity, utilization |
| `GET /map/authorities?year=&metric=` | GeoJSON FeatureCollection with the metric on each feature |
| `GET /forecasts?level=&code=` | Forecast series with intervals and backtest MAPE |
| `GET /quality/latest` and `GET /quality/runs` | Latest check results and run history |
| `GET /dictionary` | Data dictionary (tables, columns, types, descriptions, sources) |
| `GET /briefing?year=` | Briefing note content as JSON |
| `GET /briefing/export?year=&format=docx` | Briefing note as a Word file |
| `GET /export/schools?format=csv\|xlsx&...filters` | The filtered school table as a download |
| `GET /health` | Status, database connection, last pipeline run time |

### Pages (Next.js)

1. **Overview (`/`):** KPI cards, a 10-year provincial enrolment line with the forecast as a dashed line and shaded band, top 10 authorities by utilization (bar chart), and a callout listing how many schools are over 85% and over 100%.
2. **Map (`/map`):** a choropleth of authorities coloured by utilization (or enrolment change), a year slider, a legend, and a side panel when an authority is clicked. Optional Edmonton Public school points.
3. **Authorities (`/authorities`, `/authorities/[code]`):** a sortable table, then a detail page with trend plus forecast, backtest accuracy, and the authority's schools.
4. **Schools (`/schools`, `/schools/[code]`):** search, filters (authority, utilization range, year), utilization badges (green under 85%, amber 85–100%, red over 100%), "Export to Excel" and "Export to CSV", and a school page with enrolment by grade.
5. **Data quality (`/quality`):** latest run status, a pass/warn/fail table per check with failed-row samples, run history, and the pipeline lineage as a Mermaid diagram.
6. **Data dictionary (`/dictionary`):** searchable list of every table and column.
7. **Briefing (`/briefing`):** a one-page note for a chosen year, written from a fixed template filled with SQL results (no LLM, so every number is traceable). It covers 3 key findings, the 5 most pressured authorities, the outlook, and data caveats. Includes a "Download as Word" button.

### Build phases

| Phase | Build | Done when |
| --- | --- | --- |
| 0 | Scaffold repo, Docker Compose (PostGIS image), `make data` downloader, `docs/source_mapping.md` | `docker compose up` starts the database; all source files downloaded and mapped |
| 1 | Extract and load raw tables with Pandas and GeoPandas; `ops.pipeline_run` logging | Raw row counts match the source files |
| 2 | dbt project: staging and mart models, dbt tests, dbt docs | `dbt build` passes; star schema queryable |
| 3 | Quality checks into `ops.dq_result` | Checks run inside `make pipeline` and report clearly |
| 4 | Forecasts plus backtest; 2 notebooks: `01_utilization_analysis.ipynb`, `02_forecasting.ipynb`, written as teaching material | Forecast table filled; notebooks run top to bottom |
| 5 | FastAPI endpoints, schemas, tests | Every endpoint tested; `/docs` works |
| 6 | Next.js app: layout, all 7 pages, design rules | Every page works with real data, loading, empty and error states |
| 7 | Briefing generator, Word export, Excel and CSV exports | Downloads open correctly in Word and Excel |
| 8 | Playwright journey test, CI, README with screenshots | CI green; a fresh clone runs in 5 commands |

### Definition of done

- [ ] `make setup && make data && make pipeline && make dev` runs the full app on a fresh machine with Docker.
- [ ] Dashboard numbers match a manual check against the source Excel for 3 schools and 2 authorities (write the check in `docs/PROGRESS.md`).
- [ ] All quality checks visible on `/quality`; no silent failures.
- [ ] Forecast page shows backtest accuracy.
- [ ] Briefing note downloads as Word with correct numbers.
- [ ] CI green; README complete with screenshots.

### Resume bullets (use the real numbers once built)

```latex
\item Built a Python (Pandas) ELT pipeline loading 10 years of Alberta enrolment, capacity and boundary data into PostgreSQL.
\item Modelled a star-schema warehouse with dbt, with automated data quality tests and a published data dictionary.
\item Forecast 3-year enrolment and utilization by school authority, flagging schools above the 85\% utilization target.
\item Built a FastAPI and Next.js self-service dashboard with PostGIS maps, Excel export and auto-generated briefings.
```

## Sources

- [Alberta: Student population statistics](https://www.alberta.ca/student-population-statistics)
- [Student enrolment by school, authority and grade level (open data mirror)](https://donnees.iriu.ca/en/dataset/ccbcf0fb-615e-44a0-b7ec-681e2ea4e1e7)
- [School jurisdiction schools with total capacity and utilization (open data mirror)](https://donnees.iriu.ca/en/dataset/b4dbda20-2e75-4365-8b45-2f5c372fcf03)
- [Alberta School Authority Boundaries 2025 (ArcGIS REST)](https://geospatial.alberta.ca/titan/rest/services/Education_Maps/edu_public_schl_auth_bound_2025_group_public/MapServer)
- [Edmonton Public School Division school locations 2025–26 (ArcGIS FeatureServer)](https://azimuth.epsb.ca/server/rest/services/Hosted/Schools__2025/FeatureServer)
- [Alberta Education School Capital Manual 2022/23 (PDF)](https://open.alberta.ca/dataset/46c00893-b476-4e89-b9ab-329c0df35c5f/resource/8f422d8e-61b2-40f4-b689-a0ec299188b2/download/edc-school-capital-manual-2022.pdf)
- [CBE Three-Year System Student Accommodation Plan (PDF)](https://www.cbe.ab.ca/FormsManuals/Three-Year-System-Student-Accommodation-Plan.pdf)
- [CBE: utilization and the province's 85% optimal rate](https://www.cbe.ab.ca/go/28cddf85-29f0-53b8-b9a2-ddc55c0462f7)

These links came from a web search on November 21, 2026. Phase 0 of each project confirms they still download; the original datasets live on open.alberta.ca.
