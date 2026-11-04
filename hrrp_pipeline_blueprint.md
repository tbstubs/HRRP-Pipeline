# HRRP Pipeline — Design Blueprint

CMS Hospital Quality & Readmission Analytics

**Stack:** Python (Pandas) → Snowflake → dbt → Power BI

> Design document. Originally drafted April 2026 — figures and market data
> carry that date unless restated. Build order was revised 2026-09-08; see §6.

# 1. Design Context

## **1.1 What Has Been Decided**

- Power BI as the BI layer — widest enterprise adoption among the major BI tools
- PL-300 certification should follow project completion, not precede it
- Healthcare is the right sector focus for Boston (Mass General Brigham, Dana-Farber, Beth Israel, Tufts Medical Center)
- CMS public data is the right source (no scraping, no ToS risk, public domain, rich and messy enough for real transformation work)
- No scraper needed — CMS publishes direct download links; this project demonstrates pipeline architecture, not browser automation
- Snowflake is the highest-value single addition — it is what moves the stack from analyst tooling into analytics engineering
- dbt is a Tier 2 enhancement — build core pipeline first, then add dbt models for business logic layer

## **1.2 Architecture Rationale: Separation of Concerns**

Each layer in this pipeline handles problems unique to its position. This is not redundancy — it is the production architecture pattern that scales. Why each layer exists:

- Pandas: Owns source-specific messiness (CSV parsing, null standardization, type casting, column renaming). If CMS changes their file format, only this layer changes.
- Snowflake: Owns storage and serves as the single source of truth. Clean, typed tables that any downstream tool can query.
- dbt (Tier 2): Owns business logic in version-controlled, tested SQL. Definitions like “high-risk hospital” or “peer group” live here, not in a .pbix file or a Python script.
- Power BI: Owns visualization and user interaction only. Connects to Snowflake, reads modeled tables, does only display-layer calculations. Stays “thin” so the dashboard can be swapped for Tableau or Looker without losing business logic.

# 2. Domain Background: Hospital Readmissions

Hospital readmissions are the single most financially consequential quality metric in US healthcare. The CMS Hospital Readmissions Reduction Program (HRRP) penalizes hospitals with higher-than-expected 30-day readmission rates by reducing Medicare reimbursement — directly impacting revenue.

**Current Market Conditions (As of April 2026)**

- For FY 2026, 240 hospitals (8.1%) face readmission penalties of 1% or more — the first increase in five years
- For FY 2027, CMS is adding Medicare Advantage beneficiaries to all six readmission measures, shortening performance periods from 3 to 2 years, and removing COVID-19 exclusions
- Industry analysts estimate 75–82% of hospitals could see penalties under the new rules, with average penalties rising to approximately 0.44%
- Every major Boston hospital system is actively investing in analytics teams to monitor and reduce readmission rates
# **3. CMS Datasets to Use**

All datasets are available from the CMS Provider Data Catalog (data.cms.gov/provider-data/topics/hospitals). All are public domain, updated quarterly, available as CSV bulk downloads, and require no API key or authentication.

## **3.1 Primary Datasets**

**Dataset 1: Unplanned Hospital Visits (Readmissions)**

**What it contains:** Hospital-level 30-day readmission rates by condition — heart failure, pneumonia, COPD, hip/knee replacement, coronary artery bypass graft, total hip/knee arthroplasty.

**Why it matters:** This is the core HRRP penalty dataset. It contains the actual performance scores CMS uses to calculate financial penalties.

**Key fields:** Facility ID (CCN), Facility Name, State, Measure ID, Measure Name, Score, Denominator, Compared to National benchmarks.

**Cleaning challenges:** "Not Available" strings in numeric columns, suppressed data for small sample sizes, inconsistent measure naming across quarters.

**Dataset 2: Hospital General Information**

**What it contains:** Hospital metadata — location, type (acute care, critical access, children’s), ownership (government, proprietary, voluntary nonprofit), emergency services availability, bed count categories.

**Why it matters:** This becomes your dimension table. It enables filtering and grouping by hospital characteristics — essential for meaningful analysis.

**Key fields:** Facility ID (CCN), Hospital Name, Address, City, State, ZIP, County, Phone, Hospital Type, Hospital Ownership, Emergency Services, Hospital Overall Rating.

**Dataset 3: Healthcare Associated Infections (HAI)**

**What it contains:** Standardized Infection Ratios (SIRs) for central line infections, catheter infections, surgical site infections, C. diff, and MRSA.

**Why it matters:** HAI rates are a complementary quality signal. Correlating infection rates with readmission rates reveals deeper quality patterns and creates a richer analytical story.

**Dataset 4: HCAHPS (Patient Experience Survey)**

**What it contains:** Patient satisfaction scores across dimensions: communication with nurses, communication with doctors, responsiveness of hospital staff, cleanliness, quietness, discharge information, care transition, overall rating.

**Why it matters:** Patient experience is increasingly correlated with readmission outcomes in CMS’s value-based care framework. Including this data supports a multi-dimensional quality dashboard.

## **3.2 How the Datasets Connect**

All four datasets join on Facility ID (CMS Certification Number / CCN). Hospital General Information serves as the dimension table; the other three are fact tables with measure-level records. This is a genuine multi-table data modeling problem with real-world join complexity.

# **4. Full Pipeline Architecture**

## **4.1 Architecture Diagram (Text Representation)**

Create this as an actual diagram for your GitHub README (draw.io, Lucidchart, or Mermaid):

```text
CMS Provider Data Catalog (CSV Downloads)
│
▼
[Python / Pandas Ingestion Layer]
• Download CSVs from data.cms.gov
• Parse, type-cast, null-standardize
• Rename columns to snake_case
• Output: clean .parquet or .csv files
│
▼
[Snowflake — Raw / Staging Layer]
• HEALTHCARE_RAW schema
• Stage + COPY INTO from S3 or local
• Raw tables: raw_readmissions, raw_hospitals,
raw_infections, raw_patient_experience
│
▼
[dbt — Transformation Layer] (Tier 2)
• Staging models: stg_readmissions, stg_hospitals
• Intermediate: int_hospital_quality_composite
• Marts: fct_readmissions, dim_hospitals,
fct_infections, fct_patient_experience
• Tests: not_null, unique, accepted_values
│
▼
[Power BI — Presentation Layer]
• Live connection to Snowflake mart tables
• Published to Power BI Service
• Shareable link in the README
```

# **5. Step-by-Step Implementation Guide**

## **Phase 1: Data Ingestion (Python / Pandas)**

**Estimated time:** 1–2 days

**Deliverable:** Python module that downloads, validates, and cleans CMS data

**Step 1: Set Up Project Structure**

```text
healthcare-etl-pipeline/
├── src/
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── downloader.py        # CMS CSV download logic
│   │   └── transformer.py       # Pandas cleaning logic
│   ├── loading/
│   │   └── snowflake_loader.py  # Snowflake COPY INTO
│   └── pipeline.py              # Orchestration
├── dbt_project/                 # dbt models (Phase 3)
├── tests/
│   ├── test_transformer.py
│   └── test_downloader.py
├── data/                        # .gitignore this folder
├── docs/
│   └── architecture.png
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

**Step 2: Build the Downloader Module (src/ingestion/downloader.py)**

- Navigate to data.cms.gov/provider-data/topics/hospitals
- Identify the direct CSV download URLs for each of the four datasets
- Write a Python function that downloads each CSV using the requests library
- Add logging (use Python’s logging module, not print statements) to record download timestamps and file sizes
- Add basic validation: check that the downloaded file is not empty, has expected columns, and is valid CSV
- Save raw downloads to data/raw/ directory (this directory is .gitignored)

Key design note: Use requests, not a scraper. CMS provides direct download links. This is a deliberate architectural choice: the project demonstrates download-based ingestion rather than browser automation.

**Step 3: Build the Transformer Module (src/ingestion/transformer.py)**

This is where the Pandas work lives. For each dataset, create a cleaning function:

- Readmissions transformer:
- Replace "Not Available" strings with NaN
- Cast Score, Denominator columns to numeric types
- Standardize Measure ID codes (strip whitespace, uppercase)
- Add a load_date column with the current date
- Rename all columns to snake_case (e.g., "Facility ID" becomes "facility_id")
- Filter to relevant states or keep national (configurable)
- Hospital General Info transformer:
- Standardize hospital type values (some have inconsistent casing)
- Parse ZIP codes to 5-digit format (some include ZIP+4)
- Cast overall hospital rating to integer (handle "Not Available")
- Deduplicate by CCN (some quarterly files have overlap)
- HAI transformer:
- Parse Compared to National values into categorical codes
- Cast SIR scores to float, handle suppressed values
- Standardize measure names across quarterly releases
- HCAHPS transformer:
- Parse percentage responses from strings to floats
- Handle "Fewer than 100 surveys" suppression flag
- Normalize survey dimension names
- Write unit tests in tests/test_transformer.py for each transformer function. Test edge cases: empty dataframes, all-null columns, unexpected column names.

**Step 4: Build the Pipeline Orchestrator (src/pipeline.py)**

- Create a main function that calls: download → transform → save cleaned files
- Add error handling: if one dataset fails, log the error and continue with others
- Save cleaned output as Parquet files to data/cleaned/ (Parquet preserves types and is efficient for Snowflake loading)
- Add a command-line interface (argparse) so the pipeline can be run with options (e.g., --dataset readmissions --state MA)

## **Phase 2: Snowflake Warehouse**

**Estimated time:** 1–2 days

**Deliverable:** Snowflake database with raw and staging tables, data loaded from Phase 1

**Cost:** Free trial — 30 days, $400 in credits (more than sufficient)

**Step 1: Set Up Snowflake Account**

- Sign up for Snowflake free trial at signup.snowflake.com
- Choose Enterprise edition (more features to learn with, same free credits)
- Choose AWS as cloud provider, US East (closest to Boston)
- Create a worksheet and run the initial setup SQL below

**Step 2: Create Database Architecture**

Run this SQL in your Snowflake worksheet to create the database structure:

```sql
-- Database
CREATE DATABASE healthcare_analytics;
USE DATABASE healthcare_analytics;
-- Schemas (separation of raw vs. modeled)
CREATE SCHEMA raw;        -- Landing zone for Pandas output
CREATE SCHEMA staging;    -- dbt staging models (Phase 3)
CREATE SCHEMA marts;      -- dbt mart models (Phase 3)
-- Warehouse (compute)
CREATE WAREHOUSE healthcare_wh
WITH WAREHOUSE_SIZE = 'X-SMALL'
AUTO_SUSPEND = 60
AUTO_RESUME = TRUE;
```

**Step 3: Create Raw Tables**

Define the raw table schemas. These match the cleaned Pandas output exactly:

```sql
CREATE TABLE raw.readmissions (
facility_id VARCHAR,
facility_name VARCHAR,
state VARCHAR,
measure_id VARCHAR,
measure_name VARCHAR,
score FLOAT,
denominator INTEGER,
compared_to_national VARCHAR,
load_date DATE
);
-- Repeat pattern for: raw.hospitals, raw.infections,
-- raw.patient_experience
-- (Columns will match your Pandas transformer output)
```

**Step 4: Load Data from Pandas Output**

Two approaches (choose based on comfort level):

**Option A (Simpler):** SnowSQL CLI or Snowflake web UI file upload

- Install SnowSQL (Snowflake’s command-line client)
- Use PUT command to upload Parquet/CSV files to a Snowflake internal stage
- Use COPY INTO to load from stage into raw tables

```sql
PUT file:///path/to/data/cleaned/readmissions.parquet @raw.%readmissions;
COPY INTO raw.readmissions FROM @raw.%readmissions FILE_FORMAT = (TYPE = PARQUET);
```

**Option B (More Impressive):** Python snowflake-connector-python in your pipeline

- Add snowflake-connector-python to requirements.txt
- Write src/loading/snowflake_loader.py that connects to Snowflake and uses write_pandas() to load DataFrames directly
- Add Snowflake credentials to .env (never commit this file)
- Update pipeline.py to call the loader after transformation

Option B is recommended — it demonstrates end-to-end Python pipeline orchestration and adds the snowflake-connector keyword to your project.

**Step 5: Validate Loaded Data**

- Run basic count checks: SELECT COUNT(*) FROM raw.readmissions
- Run sample queries: SELECT * FROM raw.readmissions WHERE state = 'MA' LIMIT 10
- Verify types: SELECT TYPEOF(score), TYPEOF(denominator) FROM raw.readmissions LIMIT 1
- Check for nulls: SELECT COUNT(*) FROM raw.readmissions WHERE score IS NULL

## **Phase 3: dbt Transformation Layer (Tier 2 Enhancement)**

**Estimated time:** 2–3 days

**Deliverable:** dbt project with staging models, business logic models, and data tests

**When to do this:** AFTER Phases 1–2 are working and AFTER you have a basic Power BI dashboard connected. dbt is the polish layer, not the foundation.

**Step 1: Install and Initialize dbt**

- Install dbt-snowflake: pip install dbt-snowflake
- Initialize project: dbt init healthcare_analytics (inside your dbt_project/ directory)
- Configure profiles.yml with your Snowflake connection details
- Test connection: dbt debug

**Step 2: Create Staging Models**

Staging models are 1:1 with raw tables. They rename, recast, and standardize but add no business logic:

```sql
-- models/staging/stg_readmissions.sql
SELECT
facility_id,
facility_name,
state,
measure_id,
measure_name,
score AS readmission_rate,
denominator AS patient_count,
compared_to_national AS national_comparison,
load_date
FROM {{ source('raw', 'readmissions') }}
WHERE score IS NOT NULL  -- exclude suppressed records
```

**Step 3: Create Business Logic Models**

This is where the value of dbt becomes clear. Define reusable business logic:

```sql
-- models/marts/dim_hospitals.sql
-- Dimension table: one row per hospital with all attributes
-- models/marts/fct_readmissions.sql
-- Fact table: readmission rates joined with hospital attributes
-- models/marts/int_hospital_quality_composite.sql
-- Intermediate model: combines readmission + infection + patient
-- experience into a composite quality score per hospital
-- models/marts/fct_ma_hospital_comparison.sql
-- Massachusetts-specific: MA hospitals vs. national benchmarks
-- with penalty risk tier classification
```

**Step 4: Add dbt Tests**

- Add schema.yml files with tests for every model
- Required tests: not_null on facility_id, unique on facility_id in dim_hospitals, accepted_values on state (valid US state codes), relationships between fact and dimension tables
- Add custom test: no readmission rate should exceed 100% (data quality check)
- Run tests: dbt test

**Step 5: Add dbt Documentation**

- Add descriptions to every model and column in schema.yml
- Generate docs: dbt docs generate
- Serve locally to verify: dbt docs serve

dbt documentation demonstrates data governance and team collaboration practice, not just technical execution.

## **Phase 4: Power BI Dashboard**

**Estimated time:** 2–3 days

**Deliverable:** Published Power BI dashboard on Power BI Service with shareable link

**Step 1: Connect Power BI to Snowflake**

- Open Power BI Desktop (free download from Microsoft)
- Get Data → Snowflake
- Enter your Snowflake account URL and warehouse name
- Connect to the marts schema (or raw schema if dbt is not yet built)
- Import the mart tables: dim_hospitals, fct_readmissions, fct_infections, fct_patient_experience

**Step 2: Build the Data Model in Power BI**

- In Model view, verify relationships: all fact tables connect to dim_hospitals on facility_id
- Keep the model star schema — dim_hospitals in the center, fact tables radiating out
- Do NOT add transformation logic in Power Query — the data should arrive clean from Snowflake. Power Query should be essentially empty (just the connection).

**Step 3: Design the Dashboard**

Recommended dashboard layout (3–4 pages):

**Page 1: Executive Overview**

- KPI cards: Total hospitals analyzed, national average readmission rate, number of hospitals above penalty threshold
- Map visual: US map with hospitals colored by readmission performance (green/yellow/red)
- Slicer: State filter (default to Massachusetts)
- Bar chart: Top 10 hospitals by readmission rate in selected state

**Page 2: Readmission Deep Dive**

- Line chart: Readmission rate trends by condition over time (if using multiple quarterly releases)
- Clustered bar chart: Readmission rates by condition (heart failure, pneumonia, COPD, etc.)
- Table: Hospital-level detail with conditional formatting (above/below national benchmark)
- Slicer: Condition filter, Hospital Type filter

**Page 3: Quality Composite**

- Scatter plot: Readmission rate vs. infection rate (reveals quality correlation)
- Matrix: Hospital quality scorecard combining readmission, infection, and patient experience scores
- Tooltip: Hover to show hospital details and all quality dimensions

**Page 4 (Optional): Massachusetts Focus**

- Focused view on MA hospitals only
- Comparison to national averages with visual indicators
- Penalty risk tier classification (from dbt model)

**Step 4: DAX Measures (Display Layer Only)**

These are the only calculations that belong in Power BI — presentation-specific measures:

```dax
Avg Readmission Rate = AVERAGE(fct_readmissions[readmission_rate])
Above National Benchmark =
COUNTROWS(FILTER(fct_readmissions,
fct_readmissions[national_comparison] = "Worse"))
YoY Change = [Current Period Rate] - [Prior Period Rate]
-- Only if using multiple quarterly data loads
```

Note: Business logic like penalty risk classification belongs in dbt, not DAX. DAX handles only display formatting, conditional colors, and visual-specific aggregations.

**Step 5: Publish to Power BI Service**

- Sign up for Power BI Service (free tier is sufficient for portfolio use)
- Publish from Power BI Desktop → Publish → My Workspace
- Set up a scheduled refresh if using Snowflake live connection (or use Import mode for free tier)
- Generate a shareable link for the README
- Verify the dashboard renders correctly in a browser (not just Desktop)

## **Phase 5: GitHub Repository & Documentation**

**Estimated time:** Half day

**Deliverable:** Professional GitHub repo with README, architecture diagram, and clean code

**Step 1: Prepare the Repository**

- Initialize git repo in your project root
- Create comprehensive .gitignore: exclude .env, data/, credentials.json, *.parquet, *.csv, __pycache__, .pbix (Power BI files are binary and large)
- Add .env.example with placeholder values for all environment variables
- Add requirements.txt with pinned versions of all Python dependencies

**Step 2: Write the README**

The README is the first thing a reader sees. Structure it as:

- Project title and one-line description
- Architecture diagram (the visual diagram — this is the highest-impact single element)
- Business problem statement: what is the HRRP, why does readmission analysis matter, what question does this dashboard answer
- Tech stack section with version numbers
- Setup instructions (how to run the pipeline)
- Screenshots of the Power BI dashboard (embed 2–3 screenshots directly in README)
- Link to live Power BI dashboard
- Data source attribution: "Data sourced from CMS Provider Data Catalog (data.cms.gov). All data is public domain."
- What I would do differently section (shows growth mindset — mention Airflow for orchestration, CI/CD, more advanced dbt testing)

**Step 3: Create Architecture Diagram**

- Use draw.io (free), Lucidchart, or Mermaid.js to create a clean pipeline diagram
- Show all four layers: Ingestion → Warehouse → Transformation → Visualization
- Include technology logos if possible
- Save as docs/architecture.png and reference in README

This diagram is disproportionately high-impact for the time invested. Readers scan repos quickly — a clear architecture diagram communicates systems thinking instantly.

# 6. Build Order

| Phase | Deliverable |
|---|---|
| Phase 1 | Python/Pandas ingestion — download, clean, write Parquet |
| Phase 2 | Snowflake warehouse — raw tables loaded |
| Phase 3 | dbt — staging, marts, tests, docs |
| Phase 4 | Power BI dashboard on the mart tables |
| Phase 5 | Repository, README, architecture diagram |

**Build in that order.** `[revised 2026-09-08]` The original draft recommended
building Power BI before dbt, to have something presentable early. That is
superseded: the dashboard must sit on the dbt mart tables to support benchmark
tier slicing, so building it against raw tables first means building it twice.
Power BI is also the slowest step, since it needs the Windows VM.

# 7. Design Rationale

The questions this design should be able to answer.

**Business problem**

- What is the HRRP and why does it exist?
- How much money can readmission penalties cost a hospital? (Up to 3% of all Medicare reimbursement)
- Why are readmission rates increasing again in 2026 after five years of decline?
- What changes are coming in FY 2027 (Medicare Advantage inclusion, shorter performance periods)?

**Technical Decisions**

- Why Pandas for ingestion instead of loading CSVs directly to Snowflake? (Source-specific messiness should be isolated)
- Why Snowflake instead of just Power BI with CSV imports? (Single source of truth, scalable, team-accessible)
- Why dbt instead of Snowflake views? (Testing, documentation, version control, dependency management)
- Why is Power BI “thin” with minimal DAX? (Separation of concerns — business logic belongs in the warehouse, not the BI tool)

**What Would You Do Differently / Next Steps?**

- Add Airflow or Dagster for orchestration (currently manual pipeline runs)
- Add CI/CD with GitHub Actions to run dbt tests on every commit
- Add incremental loading in dbt (currently full refresh)
- Add more advanced dbt tests (custom SQL tests for business rules)
- Add a second data source (e.g., FRED economic data) for correlation analysis
