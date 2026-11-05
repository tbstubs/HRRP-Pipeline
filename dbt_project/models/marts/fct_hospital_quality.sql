-- Grain: one row per hospital. An aggregate fact table.
--
-- The other three facts are at facility x measure grain. This one rolls them
-- up to the hospital so the dashboard can rank, map and tier hospitals without
-- aggregating 565,000 rows on every interaction.
--
-- It is also what makes "benchmark tier" a real sliceable attribute rather
-- than a calculation living in a .pbix file.
--
-- Note on the CMS columns at the bottom: Hospital General Information
-- publishes CMS's own per-domain rollups. They are carried here for context,
-- NOT used to compute the tier, and they are NOT directly comparable to the
-- counts computed here.
--
-- MEASURED 2026-10-22, after a reconciliation test failed on 2,032 hospitals:
-- CMS's READM group spans measures this pipeline does not ingest. Facility
-- 010007 reports only OP_* measures in Unplanned Hospital Visits, yet CMS
-- records 2 worse-than-national measures in its READM group. So the CMS count
-- can exceed ours on a hospital where we hold no comparable measure at all.
--
-- The initial assumption was the opposite -- that ours would always be >=
-- CMS's, since this pipeline ingests 14 measures against CMS's group of 11.
-- That was wrong: the two counts are drawn from different populations and are
-- not directionally comparable. The reconciliation test asserting otherwise
-- was removed rather than loosened, because it encoded a false premise.

with national_rates as (

    -- National mean per measure, used as the benchmark each hospital is
    -- compared against. Percentage measures only -- see the readmissions CTE.
    select
        f.measure_id,
        avg(f.readmission_rate) as national_rate
    from {{ ref('fct_readmissions') }} f
    join {{ ref('dim_measures') }} m on f.measure_id = m.measure_id
    where m.measure_unit = 'Percentage'
      and f.readmission_rate is not null
    group by f.measure_id

),

readmissions as (

    -- SCOPED TO PERCENTAGE MEASURES. fct_readmissions mixes units in one
    -- column: READM_30_* are rates, EDAC_30_* are excess days, OP_* are
    -- outpatient visit rates. Averaging them together gave 11.01 against a
    -- true readmission average of 16.65.
    --
    -- The worse/better counts are computed by comparing each hospital's rate
    -- against the national mean for that measure, NOT from CMS's
    -- national_comparison column. MEASURED 2026-10-26: that column is 100%
    -- NULL on every READM_30_* row. Reading it produced a "penalty risk"
    -- tier built entirely from OP_* outpatient measures -- a plausible
    -- number under a label that meant something else entirely.
    --
    -- LIMITATION, stated rather than hidden: this is a simple comparison of
    -- a point estimate against the national mean. CMS's own determination
    -- uses an interval test and will not agree row for row.
    select
        f.facility_id,
        avg(f.readmission_rate)                                      as avg_readmission_rate,
        count(f.readmission_rate)                                    as readmission_measures_reported,
        count_if(f.readmission_rate > n.national_rate)               as readmission_measures_worse,
        count_if(f.readmission_rate < n.national_rate)               as readmission_measures_better
    from {{ ref('fct_readmissions') }} f
    join {{ ref('dim_measures') }} m on f.measure_id = m.measure_id
    join national_rates           n on f.measure_id = n.measure_id
    where m.measure_unit = 'Percentage'
      and f.readmission_rate is not null
    group by f.facility_id

),

readmissions_ranked as (

    -- The quartile must be computed over RATED hospitals only. Running
    -- ntile(4) across every hospital puts the 1,547 with no measures into
    -- the fourth quartile -- they sort last on a NULL rate -- which empties
    -- the worst band and pushes the genuinely worst hospitals up into the
    -- third.
    select
        *,
        ntile(4) over (order by avg_readmission_rate) as rate_quartile
    from readmissions

),

infections as (

    -- SCOPED TO THE _SIR MEASURES. See dim_measures: the HAI file carries
    -- six statistics per infection type, and only the SIR is a ratio. An
    -- unscoped average returned 2,699 where a Standardized Infection Ratio
    -- is centered on 1.0.
    --
    -- A SIR above 1.0 means more infections than predicted for a hospital of
    -- that case mix, so 1.0 is a meaningful threshold rather than an
    -- arbitrary one.
    select
        f.facility_id,
        avg(f.infection_ratio)                                             as avg_infection_ratio,
        count(f.infection_ratio)                                           as infection_measures_reported,
        count_if(f.infection_ratio > 1.0)                                  as infection_measures_worse
    from {{ ref('fct_infections') }} f
    join {{ ref('dim_measures') }} m on f.measure_id = m.measure_id
    where m.measure_unit = 'Standardised Ratio'
    group by f.facility_id

),

patient_experience as (

    select
        facility_id,
        avg(star_rating)                                                   as avg_star_rating,
        count(star_rating)                                                 as experience_measures_reported
    from {{ ref('fct_patient_experience') }}
    group by facility_id

)

select
    d.facility_id,
    d.state,
    d.hospital_type,
    d.hospital_ownership,
    d.overall_rating,

    r.avg_readmission_rate,
    r.readmission_measures_reported,
    r.readmission_measures_worse,
    r.readmission_measures_better,

    i.avg_infection_ratio,
    i.infection_measures_reported,
    i.infection_measures_worse,

    p.avg_star_rating,
    p.experience_measures_reported,

    -- Benchmark tier. The HRRP penalises hospitals performing worse than the
    -- national rate, so the count of worse-than-national readmission measures
    -- is the honest basis for a penalty-risk read. Defined here in tested SQL
    -- rather than in DAX, so the definition is version-controlled and the
    -- dashboard stays a display layer.
    -- RELATIVE STANDING, stated as exactly that.
    --
    -- MEASURED 2026-10-26. For the READM_30_* measures this file publishes
    -- the rate and nothing else: national_comparison is 100% NULL across all
    -- 33,530 rows, and so are lower_estimate and higher_estimate. No
    -- significance test is possible from this dataset, and no HRRP penalty
    -- can be predicted -- CMS computes those from excess readmission ratios
    -- published elsewhere.
    --
    -- So the tier is a quartile of the hospital's mean readmission rate
    -- against all rated hospitals. It makes no claim beyond rank, which is
    -- the strongest claim the data supports. Two earlier versions claimed
    -- more: one scored outpatient measures under a readmission label, the
    -- other called 37% of US hospitals "high penalty risk" by comparing
    -- point estimates to an average.
    case
        when r.readmission_measures_reported is null
          or r.readmission_measures_reported = 0 then 'Not Rated'
        when r.rate_quartile = 1                 then 'Best Quartile'
        when r.rate_quartile = 2                 then 'Second Quartile'
        when r.rate_quartile = 3                 then 'Third Quartile'
        else                                          'Worst Quartile'
    end as benchmark_tier,

    -- CMS's own published rollups, for reconciliation only.
    h.cms_readm_better,
    h.cms_readm_no_different,
    h.cms_readm_worse,

    d.load_date

from {{ ref('dim_hospitals') }}      d
left join readmissions_ranked        r on d.facility_id = r.facility_id
left join infections                 i on d.facility_id = i.facility_id
left join patient_experience         p on d.facility_id = p.facility_id
left join {{ ref('stg_hospitals') }} h on d.facility_id = h.facility_id
