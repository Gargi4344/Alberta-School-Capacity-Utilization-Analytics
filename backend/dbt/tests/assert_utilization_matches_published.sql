-- Where the school has a single capacity row, the computed utilization, rounded the
-- way the source rounds (2 decimals, half up: 190 / 400 = 0.475 -> 0.48), must equal
-- the printed value exactly.
select school_code, school_year, utilization_rate, published_utilization_rate
from {{ ref('fact_capacity') }}
where published_utilization_rate is not null
  and round(utilization_rate::numeric, 2) <> round(published_utilization_rate::numeric, 2)
