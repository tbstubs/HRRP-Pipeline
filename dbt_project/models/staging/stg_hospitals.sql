-- Rename and recast only. No business logic belongs in staging.
select
    facility_id,
    facility_name                                    as hospital_name,
    address,
    city_town                                        as city,
    state,
    zip_code,
    county_parish                                    as county,
    hospital_type,
    hospital_ownership,
    emergency_services,
    meets_criteria_for_birthing_friendly_designation as birthing_friendly,
    hospital_overall_rating                          as overall_rating,

    -- CMS publishes its own per-domain measure rollups on this file. They are
    -- measurements of a hospital, not attributes of one, so they are carried
    -- through to fct_hospital_quality rather than into dim_hospitals.
    count_of_readm_measures_better       as cms_readm_better,
    count_of_readm_measures_no_different as cms_readm_no_different,
    count_of_readm_measures_worse        as cms_readm_worse,
    count_of_safety_measures_better      as cms_safety_better,
    count_of_safety_measures_worse       as cms_safety_worse,
    count_of_mort_measures_better        as cms_mort_better,
    count_of_mort_measures_worse         as cms_mort_worse,

    load_date
from {{ source('raw', 'hospitals') }}
