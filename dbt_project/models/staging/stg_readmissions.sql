select
    facility_id,
    measure_id,
    measure_name,
    compared_to_national as national_comparison,
    score                as readmission_rate,
    denominator          as eligible_discharges,
    lower_estimate,
    higher_estimate,
    number_of_patients,
    number_of_patients_returned,
    start_date           as measure_start_date,
    end_date             as measure_end_date,
    load_date
from {{ source('raw', 'readmissions') }}
