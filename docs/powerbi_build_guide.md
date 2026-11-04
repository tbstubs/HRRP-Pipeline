# Power BI build guide — Phase 4

Everything needed to build the dashboard on the Windows VM. The warehouse is
already built and tested; this layer only displays it.

---

## 1. Connect

**Get Data → Snowflake**

| Field | Value |
|---|---|
| Server | `unovlio-hq88430.snowflakecomputing.com` |
| Warehouse | `HEALTHCARE_WH` |
| Database | `HEALTHCARE_ANALYTICS` |

Credentials: Snowflake username and password (the same ones in `.env`).

### Choose **Import**, not DirectQuery

This matters more than it looks. The Snowflake trial expires in 30 days. With
DirectQuery the dashboard goes blank the moment it does; with Import the data is
cached inside the `.pbix` and the artifact keeps working permanently.

---

## 2. Import these six tables from `MARTS`

| Table | Rows | Role |
|---|---|---|
| `DIM_HOSPITALS` | 5,419 | dimension |
| `DIM_MEASURES` | 118 | dimension |
| `FCT_READMISSIONS` | 67,060 | fact |
| `FCT_INFECTIONS` | 172,440 | fact |
| `FCT_PATIENT_EXPERIENCE` | 325,720 | fact |
| `FCT_HOSPITAL_QUALITY` | 5,419 | aggregate fact |

**Do not import from `RAW` or `STAGING`.** Those are upstream layers; the marts
are the contract.

**Leave Power Query empty.** The data arrives clean and typed. Any transform
step here is business logic escaping from dbt, where it is version-controlled
and tested, into a binary file where it is neither.

---

## 3. Verify the model

In **Model view**, confirm these relationships exist (Power BI usually detects
them; verify rather than assume):

```
                    DIM_MEASURES
                         │ measure_id
       ┌─────────────────┼─────────────────┐
       │                 │                 │
FCT_READMISSIONS   FCT_INFECTIONS   FCT_PATIENT_EXPERIENCE
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │ facility_id
                    DIM_HOSPITALS
                         │ facility_id
                 FCT_HOSPITAL_QUALITY
```

- All four facts join `DIM_HOSPITALS` on `facility_id`, **many-to-one**
- The three measure-grain facts join `DIM_MEASURES` on `measure_id`, **many-to-one**
- `FCT_HOSPITAL_QUALITY` is **one-to-one** with `DIM_HOSPITALS`
- Cross-filter direction: **single**, from dimension to fact

**Hide the duplicated columns.** `FCT_HOSPITAL_QUALITY` repeats `state`,
`hospital_type`, `hospital_ownership` and `overall_rating` for query
convenience. Right-click → Hide in report view, so there is one obvious place
to slice from.

---

## 4. The four pages

### Page 1 — Executive Overview

| Visual | Fields |
|---|---|
| **Card** (`123` icon) | `[Hospitals Analysed]` |
| **Card** | `[Avg Readmission Rate]` |
| **Card** | `[Hospitals At Penalty Risk]` |

> Use **Card**, not the visual named **KPI**. KPI requires a Trend axis as well
> as a Value, and errors with *"Fields for both Value and Trend axis are
> needed"* without one. This data is a single snapshot with no time series to
> trend across. KPI becomes useful only if multiple quarterly releases are
> loaded later.
| Geography | **Filled Map**, or a bar chart — see the notes below |
| Slicer | `DIM_HOSPITALS[state]` |
| Bar chart | Top 10 `DIM_HOSPITALS[hospital_name]` by `[Avg Readmission Rate]` |

> **Maps are optional and often disabled.** If the visual shows *"Map and
> filled map visuals are disabled"*, enable it under File > Options and
> settings > Options > Global > Security, then **restart Power BI Desktop** —
> the setting does not apply to a running session.
>
> If it still fails, use a **clustered bar chart** of `state` by
> `[Avg Readmission Rate]`, sorted descending. Nothing in the spec requires a
> map, and 50 sorted bars read better than 50 bubbles.
>
> Note the two map visuals differ: **Map** plots bubbles; **Filled Map**
> shades regions. Recent Power BI versions have **no Color saturation well** —
> shade via Format pane > Fill colors > the **fx** button > Format style
> *Gradient*, based on `[Avg Readmission Rate]`.
>
> **Filter any map to `DIM_HOSPITALS[region_type] = "State"`** (add
> `"District"` for DC). CMS reports on American Samoa, Guam, the Northern
> Mariana Islands, Puerto Rico and the US Virgin Islands — 65 real hospitals
> that span ~160 degrees of longitude. Auto-zoom fits the data extent, so with
> them included the map frames the entire globe and the continental US is
> unreadable. Guam in particular looks like a data error sitting near
> Australia; it is not.

### Page 2 — Readmission Deep Dive

| Visual | Fields |
|---|---|
| Clustered bar | `DIM_MEASURES[clinical_condition]` by `[Avg Readmission Rate]` |
| Table | `hospital_name`, `clinical_condition`, `readmission_rate`, `national_comparison` — conditional formatting on the rate |
| Slicer | `DIM_MEASURES[clinical_condition]` |
| Slicer | `DIM_HOSPITALS[hospital_type]` |

> **Filter this page to `DIM_MEASURES[measure_unit] = "Percentage"`.**
> `FCT_READMISSIONS` mixes units in one column: `READM_30_*` are percentages,
> but `EDAC_30_*` are *excess days in acute care*, a day count ranging −98.7 to
> 235.5. Averaging them together is meaningless. `measure_unit` exists in dbt
> precisely so this is a column filter rather than a rule reimplemented in DAX.

### Page 3 — Quality Composite

| Visual | Fields |
|---|---|
| Scatter | X `avg_readmission_rate`, Y `avg_infection_ratio`, from `FCT_HOSPITAL_QUALITY` |
| | Legend `benchmark_tier`, size `experience_measures_reported` |
| Matrix | Rows `hospital_name`; values `avg_readmission_rate`, `avg_infection_ratio`, `avg_star_rating` |
| Slicer | `DIM_HOSPITALS[hospital_ownership]` |

### Page 4 — Massachusetts Focus

| Visual | Fields |
|---|---|
| Filter | Page-level: `DIM_HOSPITALS[state] = "MA"` |
| Donut / bar | Count of hospitals by `benchmark_tier` |
| Table | MA hospitals with `avg_readmission_rate` vs `[National Avg Readmission Rate]` |
| Card | MA average vs national |

---

## 5. DAX — display layer only

### Put every measure on a dedicated `_Measures` table

**Home → Enter Data**, leave one column, name the table `_Measures`, Load. Then
create each measure with that table selected, and hide the dummy column.

A measure's home table is purely organisational — it does not affect the
calculation — but keeping them together means they do not scatter across six
tables. The leading underscore sorts it to the top of the Fields pane.

> **Not `DIM_MEASURES`.** That is a data table describing CMS *clinical*
> measures — readmission rates, infection ratios. The word collision is
> unfortunate; they are unrelated things.

Keep this list short. Anything that defines a business concept belongs in dbt.

```dax
Hospitals Analysed =
COUNTROWS ( DIM_HOSPITALS )

Avg Readmission Rate =
CALCULATE (
    AVERAGE ( FCT_READMISSIONS[readmission_rate] ),
    DIM_MEASURES[measure_unit] = "Percentage"
)

National Avg Readmission Rate =
CALCULATE (
    AVERAGE ( FCT_READMISSIONS[readmission_rate] ),
    DIM_MEASURES[measure_unit] = "Percentage",
    ALL ( DIM_HOSPITALS )
)

Hospitals At Penalty Risk =
CALCULATE (
    COUNTROWS ( FCT_HOSPITAL_QUALITY ),
    FCT_HOSPITAL_QUALITY[benchmark_tier]
        IN { "High Penalty Risk", "Moderate Penalty Risk" }
)
```

`benchmark_tier` is **not** computed in DAX — it is defined in
`fct_hospital_quality.sql`, version-controlled and covered by an
`accepted_values` test. That separation is the point of the architecture and is
worth being able to explain.

---

## 6. Save

Save the `.pbix` into `docs/`. It is deliberately **not** gitignored — a
reviewer should be able to download and open it.

Before committing one, check it: an Import-mode `.pbix` embeds both the data
and the Snowflake account identifier.
