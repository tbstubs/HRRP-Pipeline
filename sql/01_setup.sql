-- HRRP pipeline: one-time Snowflake setup.
-- Run this once, in a Snowsight worksheet, before loading any data.

CREATE DATABASE IF NOT EXISTS healthcare_analytics;
USE DATABASE healthcare_analytics;

-- Three schemas, one per stage of the pipeline. Keeping raw separate from
-- modelled data means a reload never touches dbt's output, and dbt can always
-- rebuild marts from an untouched source.
CREATE SCHEMA IF NOT EXISTS raw;       -- landing zone for the Pandas output
CREATE SCHEMA IF NOT EXISTS staging;   -- dbt staging models
CREATE SCHEMA IF NOT EXISTS marts;     -- dbt dimension and fact models

-- X-SMALL is the cheapest size and more than enough for ~570k rows.
-- AUTO_SUSPEND = 60 means the warehouse stops billing a minute after the last
-- query; on a 30-day trial with finite credits that matters more than warm-up
-- latency.
CREATE WAREHOUSE IF NOT EXISTS healthcare_wh
    WITH WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

USE WAREHOUSE healthcare_wh;

-- Confirm it all exists.
SHOW SCHEMAS IN DATABASE healthcare_analytics;
SHOW WAREHOUSES LIKE 'healthcare_wh';
