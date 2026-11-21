{{ config(indexes=[{'columns': ['geom'], 'type': 'gist'}]) }}
-- One row per school authority ever reported (2016-17 onward). Name and type are
-- taken from the latest year (codes are stable, names changed in 2019).
with latest as (
    select distinct on (authority_code)
        authority_code, authority_name, authority_type
    from {{ ref('stg_enrolment__authority') }}
    order by authority_code, start_year desc
),

span as (
    select
        authority_code,
        min(school_year) as first_school_year,
        max(school_year) as last_school_year,
        count(*) as years_reported
    from {{ ref('stg_enrolment__authority') }}
    group by authority_code
)

select
    l.authority_code,
    l.authority_name,
    l.authority_type,
    s.first_school_year,
    s.last_school_year,
    s.years_reported,
    s.last_school_year = (select max(last_school_year) from span) as is_active,
    b.boundary_layer,
    coalesce(b.geometry_was_repaired, false) as geometry_was_repaired,
    b.geom
from latest as l
join span as s using (authority_code)
left join {{ ref('stg_geo__authority_boundary') }} as b using (authority_code)
