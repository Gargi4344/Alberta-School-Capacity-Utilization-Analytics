-- Grain: school x school year (every year with enrolment).
-- Utilization (DECISIONS D6, D16, D17):
--   * published: the capacity group's adjusted enrolment / capacity, in years with
--     published capacity (2023-24);
--   * estimated: the group's headcount that year x its adjustment factor / the latest
--     published capacity (capacity held flat). The adjustment factor is the group's
--     adjusted enrolment / headcount in the capacity year, so the estimate equals the
--     published value in that year and follows headcount in the others;
--   * utilization_rate = published when available, else estimated (utilization_basis).
with enrol as (
    select school_code, school_year, start_year, authority_code, total_enrolment
    from {{ ref('stg_enrolment__school') }}
),

latest_capacity as (
    select distinct on (school_code)
        school_code,
        school_year as capacity_school_year,
        capacity_group_id,
        capacity,
        adjusted_enrolment
    from {{ ref('fact_capacity') }}
    order by school_code, school_year desc
),

group_enrolment as (
    select c.capacity_group_id, e.school_year, sum(e.total_enrolment) as group_enrolment
    from latest_capacity as c
    join enrol as e using (school_code)
    group by c.capacity_group_id, e.school_year
),

calibration as (
    select
        c.capacity_group_id,
        max(c.adjusted_enrolment) / nullif(max(ge.group_enrolment), 0) as adjustment_factor
    from latest_capacity as c
    join group_enrolment as ge
        on ge.capacity_group_id = c.capacity_group_id
        and ge.school_year = c.capacity_school_year
    group by c.capacity_group_id
),

joined as (
    select
        e.school_code,
        e.school_year,
        e.start_year,
        e.authority_code,
        e.total_enrolment,
        c.capacity_group_id,
        c.capacity,
        c.capacity_school_year,
        ge.group_enrolment as capacity_group_enrolment,
        cal.adjustment_factor,
        ge.group_enrolment * coalesce(cal.adjustment_factor, 1)
            as capacity_group_adjusted_enrolment,
        ge.group_enrolment * coalesce(cal.adjustment_factor, 1) / nullif(c.capacity, 0)
            as utilization_estimated,
        p.utilization_rate as utilization_published
    from enrol as e
    left join latest_capacity as c using (school_code)
    left join group_enrolment as ge
        on ge.capacity_group_id = c.capacity_group_id and ge.school_year = e.school_year
    left join calibration as cal on cal.capacity_group_id = c.capacity_group_id
    left join {{ ref('fact_capacity') }} as p
        on p.school_code = e.school_code and p.school_year = e.school_year
)

select
    *,
    coalesce(utilization_published, utilization_estimated) as utilization_rate,
    case
        when utilization_published is not null then 'published'
        when utilization_estimated is not null then 'estimated'
    end as utilization_basis,
    coalesce(utilization_published, utilization_estimated)
        >= {{ var('utilization_threshold') }} as is_over_threshold,
    coalesce(utilization_published, utilization_estimated)
        >= {{ var('over_capacity_threshold') }} as is_over_capacity
from joined
