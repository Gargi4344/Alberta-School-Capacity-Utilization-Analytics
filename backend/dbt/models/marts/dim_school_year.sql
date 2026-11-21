-- One row per school year.
{%- set preliminary = var('preliminary_school_years') %}
with years as (
    select distinct school_year, start_year
    from {{ ref('stg_enrolment__authority') }}
),

capacity_years as (
    select distinct school_year from {{ ref('int_capacity__group') }}
)

select
    y.school_year,
    y.start_year,
    {% if preliminary | length > 0 -%}
    y.school_year in ({% for s in preliminary %}'{{ s }}'{{ "," if not loop.last }}{% endfor %})
    {%- else -%}
    y.start_year = (select max(start_year) from years)
    {%- endif %} as is_preliminary,
    c.school_year is not null as has_published_capacity
from years as y
left join capacity_years as c using (school_year)
