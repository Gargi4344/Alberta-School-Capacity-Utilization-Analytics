-- Assign each matched capacity row to a capacity group (docs/DECISIONS.md D16).
--
-- A facility is (year, authority, facility name, net capacity). The source repeats a
-- shared facility's full capacity and enrolment on every school's row, and a few
-- multi-campus schools repeat the school's enrolment on every campus row. So:
--   * schools sharing a facility form one group (the facility);
--   * otherwise a school (with one or more facilities) is its own group.
-- A school that is both multi-facility and in a shared facility would break this
-- rule; tests/assert_capacity_groups_are_simple.sql fails if that ever happens.
with rows as (
    select
        *,
        md5(concat_ws('|', school_year, authority_code, facility_name, net_capacity))
            as facility_key
    from {{ ref('int_capacity__matched') }}
    where school_code is not null
),

facility_schools as (
    select facility_key, count(distinct school_code) as schools_in_facility
    from rows
    group by facility_key
),

school_facilities as (
    select school_year, school_code, count(distinct facility_key) as facilities_for_school
    from rows
    group by school_year, school_code
)

select
    r.*,
    fs.schools_in_facility,
    sf.facilities_for_school,
    case
        when fs.schools_in_facility > 1 then 'F-' || left(r.facility_key, 12)
        else 'S-' || r.school_year || '-' || r.school_code
    end as capacity_group_id
from rows as r
join facility_schools as fs using (facility_key)
join school_facilities as sf using (school_year, school_code)
