-- One row per capacity group per capacity year: capacity is summed over distinct
-- facilities, adjusted enrolment over distinct values (the source repeats shared
-- values on each row). See int_capacity__grouped for the grouping rule.
with grouped as (
    select * from {{ ref('int_capacity__grouped') }}
),

facilities as (
    select distinct capacity_group_id, school_year, authority_code, facility_key, net_capacity
    from grouped
),

capacity as (
    select
        capacity_group_id,
        school_year,
        min(authority_code) as authority_code,
        count(distinct authority_code) as authority_count,
        sum(net_capacity) as capacity,
        count(*) as facility_count
    from facilities
    group by capacity_group_id, school_year
),

enrolment as (
    select
        capacity_group_id,
        sum(distinct adj_total_enrolment) as adjusted_enrolment,
        count(distinct school_code) as school_count
    from grouped
    group by capacity_group_id
)

select
    c.capacity_group_id,
    c.school_year,
    c.authority_code,
    c.authority_count,
    c.capacity,
    e.adjusted_enrolment,
    e.adjusted_enrolment / nullif(c.capacity, 0) as utilization_rate,
    c.facility_count,
    e.school_count
from capacity as c
join enrolment as e using (capacity_group_id)
