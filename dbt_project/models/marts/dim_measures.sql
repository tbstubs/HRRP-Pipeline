-- The second conformed dimension. Every fact carries measure_id, and the
-- measure's name, domain and clinical condition are attributes OF THE MEASURE,
-- not of the hospital. Putting them here is what lets the dashboard slice by
-- condition without duplicating text on 565,000 fact rows.
with all_measures as (

    select distinct measure_id, measure_name, 'Readmissions' as measure_domain
    from {{ ref('stg_readmissions') }}

    union all

    select distinct measure_id, measure_name, 'Infections' as measure_domain
    from {{ ref('stg_infections') }}

    union all

    select distinct measure_id, measure_name, 'Patient Experience' as measure_domain
    from {{ ref('stg_patient_experience') }}

)

select
    measure_id,
    measure_name,
    measure_domain,

    -- Clinical condition, derived from the CMS measure ID convention. Only the
    -- readmission and ED-visit measures encode a condition; the others are
    -- reported at hospital level and are labeled as such rather than guessed.
    case
        when endswith(measure_id, '_HF')        then 'Heart Failure'
        when endswith(measure_id, '_AMI')       then 'Heart Attack'
        when endswith(measure_id, '_PN')        then 'Pneumonia'
        when endswith(measure_id, '_COPD')      then 'COPD'
        when endswith(measure_id, '_CABG')      then 'Cardiac Bypass'
        when endswith(measure_id, '_HIP_KNEE')  then 'Hip/Knee Replacement'
        when measure_id = 'HYBRID_HWR'          then 'Hospital-Wide'
        when startswith(measure_id, 'OP_')      then 'Outpatient Procedure'
        else 'Not Condition-Specific'
    end as clinical_condition,

    -- Unit of the measure's value. The Unplanned Hospital Visits file mixes
    -- units in one column, so averaging it without filtering on this produces
    -- a meaningless number: READM_30_* are percentages, EDAC_30_* are a count
    -- of excess days (observed -98.7 to 235.5). Putting the distinction here
    -- means the dashboard filters on a column instead of reimplementing the
    -- rule in DAX.
    case
        when startswith(measure_id, 'READM_')       then 'Percentage'
        when measure_id = 'HYBRID_HWR'              then 'Percentage'
        when startswith(measure_id, 'EDAC_')        then 'Excess Days'
        when startswith(measure_id, 'OP_')          then 'Visit Rate'
        -- The HAI file is not 36 infection ratios. It is 6 infection types
        -- times 6 statistics, and only the _SIR rows are ratios. MEASURED
        -- 2026-10-26: averaging all 36 together gave an "infection ratio" of
        -- 2,699 because HAI_5_DOPC is MRSA patient-days, averaging 41,792.
        when endswith(measure_id, '_SIR')           then 'Standardised Ratio'
        when endswith(measure_id, '_DOPC')          then 'Device Days'
        when endswith(measure_id, '_NUMERATOR')     then 'Observed Cases'
        when endswith(measure_id, '_ELIGCASES')     then 'Predicted Cases'
        when endswith(measure_id, '_CILOWER')       then 'Confidence Bound'
        when endswith(measure_id, '_CIUPPER')       then 'Confidence Bound'
        when measure_domain = 'Patient Experience'  then 'Survey Score'
        else 'Other'
    end as measure_unit

from all_measures
