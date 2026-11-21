{{ config(severity='warn') }}
-- Warn (don't fail) for capacity rows that link to no school. Expected today: the
-- Saskatchewan-side Lloydminster schools and one school no longer in enrolment
-- (docs/source_mapping.md section 3). Phase 3 reports these in ops.dq_result.
select school_year, authority_name, school_name, facility_name, match_method
from {{ ref('int_capacity__matched') }}
where school_code is null
