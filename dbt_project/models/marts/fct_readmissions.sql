-- Grain: one row per hospital per readmission measure.
select
    facility_id,
    measure_id,
    readmission_rate,
    eligible_discharges,
    lower_estimate,
    higher_estimate,
    number_of_patients,
    number_of_patients_returned,
    national_comparison,
    measure_start_date,
    measure_end_date,
    load_date
from {{ ref('stg_readmissions') }}
