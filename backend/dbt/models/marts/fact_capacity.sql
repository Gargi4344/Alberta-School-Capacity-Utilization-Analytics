-- Grain: school x school year, for years with published capacity (2023-24 today).
-- Values are the school's capacity group (DECISIONS D16). For a school with one
-- capacity row, utilization_rate equals the published value (to its 2 decimals).
with schools as (
    select
        school_code,
        school_year,
        capacity_group_id,
        count(*) as capacity_rows,
        max(published_utilization_rate) as published_utilization_rate
    from {{ ref('int_capacity__grouped') }}
    group by school_code, school_year, capacity_group_id
)

select
    s.school_code,
    s.school_year,
    g.authority_code,
    s.capacity_group_id,
    g.capacity,
    g.adjusted_enrolment,
    g.utilization_rate,
    case when s.capacity_rows = 1 then s.published_utilization_rate end
        as published_utilization_rate,
    g.facility_count,
    g.school_count as schools_in_group,
    g.school_count > 1 as shares_facility,
    g.facility_count > 1 as has_multiple_facilities
from schools as s
join {{ ref('int_capacity__group') }} as g using (capacity_group_id, school_year)
