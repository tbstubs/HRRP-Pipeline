-- Grain: one row per hospital per HCAHPS measure.
select
    facility_id,
    measure_id,
    star_rating,
    answer_percent,
    linear_mean_value,
    completed_surveys,
    response_rate_percent,
    measure_start_date,
    measure_end_date,
    load_date
from {{ ref('stg_patient_experience') }}
