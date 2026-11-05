-- A Standardized Infection Ratio is observed over predicted infections.
-- It is unbounded above but cannot be negative.
select
    facility_id,
    measure_id,
    infection_ratio
from {{ ref('fct_infections') }}
where infection_ratio is not null
  and infection_ratio < 0
