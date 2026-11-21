-- Edmonton Public school locations (optional source; empty when not loaded).
select
    school_code,
    school_name as point_school_name,
    grades as point_grades,
    geom
from {{ source('raw', 'school_point') }}
