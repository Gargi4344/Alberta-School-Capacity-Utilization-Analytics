{{ config(indexes=[{'columns': ['geom'], 'type': 'gist'}]) }}
-- One row per school ever reported. Name and authority come from the latest year
-- the school appears; grades_offered from that year's non-zero grades.
with latest as (
    select distinct on (school_code)
        school_code, school_name, authority_code, school_year as latest_school_year
    from {{ ref('stg_enrolment__school') }}
    order by school_code, start_year desc
),

span as (
    select
        school_code,
        min(school_year) as first_school_year,
        max(school_year) as last_school_year,
        count(*) as years_reported
    from {{ ref('stg_enrolment__school') }}
    group by school_code
),

grades as (
    select
        g.school_code,
        min(g.grade_order) filter (where g.grade_order >= 0) as min_grade,
        max(g.grade_order) filter (where g.grade_order >= 0) as max_grade,
        bool_or(g.grade_order = -1) as has_ungraded
    from {{ ref('stg_enrolment__school_grade') }} as g
    join latest as l on l.school_code = g.school_code and l.latest_school_year = g.school_year
    where g.headcount > 0
    group by g.school_code
)

select
    l.school_code,
    l.school_name,
    l.authority_code,
    case
        when gr.min_grade is null and gr.has_ungraded then 'Ungraded'
        when gr.min_grade is null then null
        else
            case gr.min_grade when 0 then 'ECS' else gr.min_grade::text end
            || case when gr.max_grade > gr.min_grade then '–' || gr.max_grade::text else '' end
    end as grades_offered,
    s.first_school_year,
    s.last_school_year,
    s.years_reported,
    s.last_school_year = (select max(last_school_year) from span) as is_open,
    p.geom
from latest as l
join span as s using (school_code)
left join grades as gr using (school_code)
left join {{ ref('stg_geo__school_point') }} as p using (school_code)
