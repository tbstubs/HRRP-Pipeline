-- Raw landing tables for the HRRP pipeline.
-- GENERATED from data/cleaned/*.parquet — do not edit by hand.
-- Regenerate with: python -m scripts.generate_raw_ddl

USE DATABASE healthcare_analytics;
USE SCHEMA raw;


CREATE OR REPLACE TABLE raw.hospitals (
    facility_id                                        VARCHAR,
    facility_name                                      VARCHAR,
    address                                            VARCHAR,
    city_town                                          VARCHAR,
    state                                              VARCHAR,
    zip_code                                           VARCHAR,
    county_parish                                      VARCHAR,
    telephone_number                                   VARCHAR,
    hospital_type                                      VARCHAR,
    hospital_ownership                                 VARCHAR,
    emergency_services                                 VARCHAR,
    meets_criteria_for_birthing_friendly_designation   VARCHAR,
    hospital_overall_rating                            FLOAT,
    hospital_overall_rating_footnote                   VARCHAR,
    mort_group_measure_count                           FLOAT,
    count_of_facility_mort_measures                    FLOAT,
    count_of_mort_measures_better                      FLOAT,
    count_of_mort_measures_no_different                FLOAT,
    count_of_mort_measures_worse                       FLOAT,
    mort_group_footnote                                VARCHAR,
    safety_group_measure_count                         FLOAT,
    count_of_facility_safety_measures                  FLOAT,
    count_of_safety_measures_better                    FLOAT,
    count_of_safety_measures_no_different              FLOAT,
    count_of_safety_measures_worse                     FLOAT,
    safety_group_footnote                              VARCHAR,
    readm_group_measure_count                          FLOAT,
    count_of_facility_readm_measures                   FLOAT,
    count_of_readm_measures_better                     FLOAT,
    count_of_readm_measures_no_different               FLOAT,
    count_of_readm_measures_worse                      FLOAT,
    readm_group_footnote                               VARCHAR,
    pt_exp_group_measure_count                         FLOAT,
    count_of_facility_pt_exp_measures                  FLOAT,
    pt_exp_group_footnote                              VARCHAR,
    te_group_measure_count                             FLOAT,
    count_of_facility_te_measures                      FLOAT,
    te_group_footnote                                  VARCHAR,
    load_date                                          DATE
);

CREATE OR REPLACE TABLE raw.infections (
    facility_id            VARCHAR,
    measure_id             VARCHAR,
    measure_name           VARCHAR,
    compared_to_national   VARCHAR,
    score                  FLOAT,
    footnote               VARCHAR,
    start_date             DATE,
    end_date               DATE,
    load_date              DATE
);

CREATE OR REPLACE TABLE raw.patient_experience (
    facility_id                             VARCHAR,
    measure_id                              VARCHAR,
    hcahps_question                         VARCHAR,
    hcahps_answer_description               VARCHAR,
    patient_survey_star_rating              FLOAT,
    patient_survey_star_rating_footnote     VARCHAR,
    hcahps_answer_percent                   FLOAT,
    hcahps_answer_percent_footnote          VARCHAR,
    hcahps_linear_mean_value                FLOAT,
    number_of_completed_surveys             FLOAT,
    number_of_completed_surveys_footnote    VARCHAR,
    survey_response_rate_percent            FLOAT,
    survey_response_rate_percent_footnote   VARCHAR,
    start_date                              DATE,
    end_date                                DATE,
    load_date                               DATE
);

CREATE OR REPLACE TABLE raw.readmissions (
    facility_id                   VARCHAR,
    measure_id                    VARCHAR,
    measure_name                  VARCHAR,
    compared_to_national          VARCHAR,
    denominator                   FLOAT,
    score                         FLOAT,
    lower_estimate                FLOAT,
    higher_estimate               FLOAT,
    number_of_patients            FLOAT,
    number_of_patients_returned   FLOAT,
    footnote                      VARCHAR,
    start_date                    DATE,
    end_date                      DATE,
    load_date                     DATE
);
