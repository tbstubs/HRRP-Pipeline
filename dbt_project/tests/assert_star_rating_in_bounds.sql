-- Custom bounds test. HCAHPS star ratings are a 1-5 scale by definition,
-- so anything outside it is impossible rather than merely unusual.
select
    facility_id,
    measure_id,
    star_rating
from {{ ref('fct_patient_experience') }}
where star_rating is not null
  and (star_rating < 1 or star_rating > 5)
