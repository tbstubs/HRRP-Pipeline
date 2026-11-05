select
    facility_id,
    measure_id,
    measure_name,
    compared_to_national as national_comparison,
    score                as infection_ratio,
    start_date           as measure_start_date,
    end_date             as measure_end_date,
    load_date
from {{ source('raw', 'infections') }}
