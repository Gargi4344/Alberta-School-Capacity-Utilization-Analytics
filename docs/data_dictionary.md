# Data dictionary

Filled in during Phase 2, when the dbt models exist (and served at `GET /api/v1/dictionary`). Rules already fixed in Phase 0:

| Term | Definition | Source |
| --- | --- | --- |
| `school_year` | `YYYY-YY`, taken from the source file name | DECISIONS D2 |
| `authority_code`, `school_code` | 4-digit zero-padded strings | DECISIONS D3 |
| `utilization_rate` (published) | `Adj Total Enrol ÷ Net Capacity`, as given in the capacity file (2023-24) | Capacity XLSX `Utiliz. %` |
| `utilization_rate` (school, multi-facility) | `Σ adj_total_enrolment ÷ Σ net_capacity` across the school's facilities | source_mapping.md §3 |
| `utilization_rate` (estimated) | `headcount total ÷ 2023-24 net_capacity`, flagged `is_estimated` | DECISIONS D6 |
| Utilization threshold | 85% by default (`UTILIZATION_THRESHOLD_PCT`); 100% or more is "over capacity" | Spec |
