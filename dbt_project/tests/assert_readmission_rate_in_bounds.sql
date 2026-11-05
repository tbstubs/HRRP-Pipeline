-- Custom bounds test. A dbt test is a query that must return zero rows;
-- any row it returns is a failure.
--
-- SCOPED DELIBERATELY to the READM_30_* measures. The Unplanned Hospital
-- Visits file mixes two measure families with different units, and an
-- unscoped bound was wrong on 3,857 rows:
--
--   READM_30_*  30-day readmission RATE, a percentage, 0-100
--   EDAC_30_*   Excess Days in Acute Care, a COUNT OF DAYS per 100
--               discharges. Legitimately negative (fewer days than
--               predicted is good) and legitimately above 100.
--               Observed range in the live data: -98.7 to 235.5.
--   OP_*        outpatient visit rates, separate units again
--
-- Applying a percentage bound to a day count is the kind of error a test is
-- supposed to catch, so the fix is to scope the test, not loosen the bound.
select
    facility_id,
    measure_id,
    readmission_rate
from {{ ref('fct_readmissions') }}
where measure_id like 'READM%'
  and readmission_rate is not null
  and (readmission_rate < 0 or readmission_rate > 100)
