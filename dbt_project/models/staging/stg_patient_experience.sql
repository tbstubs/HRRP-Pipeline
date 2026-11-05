select
    facility_id,
    measure_id,
    hcahps_question              as measure_name,
    hcahps_answer_description    as answer_description,
    patient_survey_star_rating   as star_rating,
    hcahps_answer_percent        as answer_percent,
    hcahps_linear_mean_value     as linear_mean_value,
    number_of_completed_surveys  as completed_surveys,
    survey_response_rate_percent as response_rate_percent,
    start_date                   as measure_start_date,
    end_date                     as measure_end_date,
    load_date
from {{ source('raw', 'patient_experience') }}
