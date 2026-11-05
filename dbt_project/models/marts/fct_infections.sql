-- Grain: one row per hospital per infection measure.
select
    facility_id,
    measure_id,
    infection_ratio,
    national_comparison,
    measure_start_date,
    measure_end_date,
    load_date
from {{ ref('stg_infections') }}
