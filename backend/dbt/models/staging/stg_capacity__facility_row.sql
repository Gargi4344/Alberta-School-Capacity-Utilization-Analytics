-- One row per school x facility, as published, plus the name-matching keys.
select
    id as capacity_row_id,
    school_year,
    authority_name,
    school_name,
    facility_name,
    facility_location,
    net_capacity,
    adj_total_enrolment,
    utilization_rate as published_utilization_rate,
    {{ normalize_name('authority_name') }} as authority_key,
    {{ normalize_name('school_name') }} as school_key,
    source_file,
    source_row
from {{ source('raw', 'capacity') }}
