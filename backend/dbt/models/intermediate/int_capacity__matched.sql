-- Capacity rows with authority_code and school_code attached.
-- The capacity file has no codes, so it joins to the same year's enrolment by
-- normalized name: authority first, then school within that authority. Only exact,
-- unambiguous matches count; a manual crosswalk seed can add confirmed links.
-- Rationale: docs/DECISIONS.md D4.
with enrol as (
    select
        school_year,
        authority_code,
        school_code,
        {{ normalize_name('authority_name') }} as authority_key,
        {{ normalize_name('school_name') }} as school_key
    from {{ ref('stg_enrolment__school') }}
),

authority_keys as (
    select distinct school_year, authority_key, authority_code
    from enrol
),

school_keys as (
    select
        school_year,
        authority_code,
        school_key,
        min(school_code) as school_code,
        count(*) as candidates
    from enrol
    group by school_year, authority_code, school_key
),

crosswalk as (
    select authority_name, school_name, school_code
    from {{ ref('capacity_school_crosswalk') }}
)

select
    cap.*,
    a.authority_code,
    coalesce(cw.school_code, case when sk.candidates = 1 then sk.school_code end) as school_code,
    case
        when cw.school_code is not null then 'crosswalk'
        when sk.candidates = 1 then 'exact_name'
        when sk.candidates > 1 then 'ambiguous_name'
        when a.authority_code is null then 'unmatched_authority'
        else 'unmatched_school'
    end as match_method
from {{ ref('stg_capacity__facility_row') }} as cap
left join authority_keys as a
    on a.school_year = cap.school_year and a.authority_key = cap.authority_key
left join school_keys as sk
    on sk.school_year = cap.school_year
    and sk.authority_code = a.authority_code
    and sk.school_key = cap.school_key
left join crosswalk as cw
    on cw.authority_name = cap.authority_name and cw.school_name = cap.school_name
