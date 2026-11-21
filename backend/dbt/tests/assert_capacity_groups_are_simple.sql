-- The capacity grouping rule (DECISIONS D16) assumes no school is both spread over
-- several facilities AND sharing a facility with another school. If a future capacity
-- file breaks that, this test fails so the rule is reviewed instead of silently wrong.
select school_year, school_code, facility_name, schools_in_facility, facilities_for_school
from {{ ref('int_capacity__grouped') }}
where schools_in_facility > 1 and facilities_for_school > 1
