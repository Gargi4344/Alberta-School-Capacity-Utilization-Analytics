-- Grain: authority x school year.
-- total_enrolment is the official authority total (all schools). Capacity and
-- utilization cover schools with published capacity only; each capacity group is
-- counted once, so shared facilities are not double counted. Estimated utilization
-- uses each group's calibrated adjusted enrolment (see fact_school_year).
with authority as (
    select authority_code, school_year, total_enrolment
    from {{ ref('stg_enrolment__authority') }}
),

schools as (
    select
        authority_code,
        school_year,
        count(*) as school_count,
        count(capacity) as schools_with_capacity,
        count(*) filter (where is_over_threshold) as schools_over_threshold,
        count(*) filter (where is_over_capacity) as schools_over_capacity
    from {{ ref('fact_school_year') }}
    group by authority_code, school_year
),

group_years as (
    -- one row per capacity group per year in which any member school has enrolment
    select distinct
        g.authority_code,
        f.school_year,
        f.capacity_group_id,
        f.capacity,
        f.capacity_group_enrolment,
        f.capacity_group_adjusted_enrolment
    from {{ ref('fact_school_year') }} as f
    join {{ ref('int_capacity__group') }} as g using (capacity_group_id)
    where f.capacity_group_id is not null
),

capacity as (
    select
        authority_code,
        school_year,
        sum(capacity) as total_capacity,
        sum(capacity_group_enrolment) as enrolment_in_capacity_schools,
        sum(capacity_group_adjusted_enrolment) as adjusted_enrolment_estimated
    from group_years
    group by authority_code, school_year
),

published as (
    select
        authority_code,
        school_year,
        sum(adjusted_enrolment) / nullif(sum(capacity), 0) as utilization_published
    from {{ ref('int_capacity__group') }}
    group by authority_code, school_year
)

select
    a.authority_code,
    a.school_year,
    a.total_enrolment,
    coalesce(s.school_count, 0) as school_count,
    coalesce(s.schools_with_capacity, 0) as schools_with_capacity,
    c.total_capacity,
    c.enrolment_in_capacity_schools,
    c.adjusted_enrolment_estimated / nullif(c.total_capacity, 0) as utilization_estimated,
    p.utilization_published,
    coalesce(
        p.utilization_published,
        c.adjusted_enrolment_estimated / nullif(c.total_capacity, 0)
    ) as utilization_rate,
    case
        when p.utilization_published is not null then 'published'
        when c.total_capacity is not null then 'estimated'
    end as utilization_basis,
    coalesce(s.schools_over_threshold, 0) as schools_over_85,
    coalesce(s.schools_over_capacity, 0) as schools_over_100
from authority as a
left join schools as s using (authority_code, school_year)
left join capacity as c using (authority_code, school_year)
left join published as p using (authority_code, school_year)
