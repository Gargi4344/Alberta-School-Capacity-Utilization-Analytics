-- The unpivoted grade rows of each school-year must add up to its published Total.
select s.school_code, s.school_year, s.total_enrolment, sum(f.headcount) as grade_sum
from {{ ref('stg_enrolment__school') }} as s
join {{ ref('fact_enrolment') }} as f using (school_code, school_year)
group by s.school_code, s.school_year, s.total_enrolment
having sum(f.headcount) <> s.total_enrolment
