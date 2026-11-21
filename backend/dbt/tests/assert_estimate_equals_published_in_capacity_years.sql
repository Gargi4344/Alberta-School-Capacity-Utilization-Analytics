-- The calibrated estimate must reproduce the published utilization exactly in the
-- capacity year, for schools and for authorities (DECISIONS D17). This keeps the
-- time series free of a method jump between estimated and published years.
select 'school' as level, school_code as code, school_year,
       utilization_estimated, utilization_published
from {{ ref('fact_school_year') }}
where utilization_published is not null
  and abs(utilization_estimated - utilization_published) > 1e-9

union all

select 'authority', authority_code, school_year, utilization_estimated, utilization_published
from {{ ref('agg_authority_year') }}
where utilization_published is not null
  and abs(utilization_estimated - utilization_published) > 1e-9
