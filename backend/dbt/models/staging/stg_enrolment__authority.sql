-- One row per authority per school year, as published.
select
    authority_code,
    school_year,
    cast(left(school_year, 4) as integer) as start_year,
    authority_name,
    lower(authority_category) as authority_type,
    total as total_enrolment,
    source_file,
    source_row
from {{ source('raw', 'enrolment_authority') }}
