-- Grain: school x school year x grade. Headcount as published (0 kept).
-- authority_code is the school's authority in that year (6 schools moved authority).
select
    g.school_code,
    g.school_year,
    g.grade,
    g.grade_order,
    s.authority_code,
    g.headcount
from {{ ref('stg_enrolment__school_grade') }} as g
join {{ ref('stg_enrolment__school') }} as s using (school_code, school_year)
