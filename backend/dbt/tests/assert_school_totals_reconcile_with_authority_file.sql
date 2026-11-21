-- School enrolment summed by authority must equal the published authority file,
-- every year and every authority (true for all 10 years at Phase 0).
with from_schools as (
    select authority_code, school_year, sum(headcount) as total
    from {{ ref('fact_enrolment') }}
    group by authority_code, school_year
),

published as (
    select authority_code, school_year, total_enrolment as total
    from {{ ref('stg_enrolment__authority') }}
)

select
    coalesce(s.authority_code, p.authority_code) as authority_code,
    coalesce(s.school_year, p.school_year) as school_year,
    s.total as from_schools,
    p.total as published
from from_schools as s
full outer join published as p using (authority_code, school_year)
where s.total is distinct from p.total
