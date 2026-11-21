-- One row per school per school year, as published (wide: one column per grade).
select
    school_code,
    school_year,
    cast(left(school_year, 4) as integer) as start_year,
    school_name,
    authority_code,
    authority_name,
    lower(authority_category) as authority_type,
    ungraded,
    ecs,
    grade_1, grade_2, grade_3, grade_4, grade_5, grade_6,
    grade_7, grade_8, grade_9, grade_10, grade_11, grade_12,
    total as total_enrolment,
    source_file,
    source_row
from {{ source('raw', 'enrolment_school') }}
