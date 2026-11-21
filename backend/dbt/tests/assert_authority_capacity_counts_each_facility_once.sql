-- In capacity years, an authority's total capacity must equal the sum over its
-- DISTINCT facilities (year, authority, facility name, net capacity) of matched rows.
-- Catches double counting of shared facilities, which the source repeats per school.
with facilities as (
    select distinct school_year, authority_code, facility_name, net_capacity
    from {{ ref('int_capacity__grouped') }}
),

expected as (
    select authority_code, school_year, sum(net_capacity) as capacity
    from facilities
    group by authority_code, school_year
)

select e.authority_code, e.school_year, e.capacity as expected, a.total_capacity as actual
from expected as e
join {{ ref('agg_authority_year') }} as a using (authority_code, school_year)
where a.total_capacity is distinct from e.capacity
