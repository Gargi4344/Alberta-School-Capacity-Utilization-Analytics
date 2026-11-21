-- Unpivot: one row per school x school year x grade (zeros kept, so every grade
-- exists for every school-year and sums are easy to reconcile).
{%- set grades = [
    ('ungraded', 'Ungraded', -1), ('ecs', 'ECS', 0),
    ('grade_1', '1', 1), ('grade_2', '2', 2), ('grade_3', '3', 3), ('grade_4', '4', 4),
    ('grade_5', '5', 5), ('grade_6', '6', 6), ('grade_7', '7', 7), ('grade_8', '8', 8),
    ('grade_9', '9', 9), ('grade_10', '10', 10), ('grade_11', '11', 11), ('grade_12', '12', 12),
] %}

select
    s.school_code,
    s.school_year,
    g.grade,
    g.grade_order,
    g.headcount
from {{ ref('stg_enrolment__school') }} as s
cross join lateral (
    values
    {%- for col, label, order in grades %}
        ('{{ label }}', {{ order }}, s.{{ col }}){{ "," if not loop.last }}
    {%- endfor %}
) as g (grade, grade_order, headcount)
