"""Clean raw CMS CSVs into typed, normalized DataFrames.

This layer owns source-specific messiness so that nothing downstream has to
know about it. If CMS changes a file format, only this module changes.

Three decisions here were made against the real files rather than the design
document, which was wrong on all three:

* Suppressed values appear as BOTH ``"Not Available"`` and ``"Not Applicable"``.
  HCAHPS uses both; the other files use only the first.
* ZIP codes are already five digits in every row of every file, so no ZIP+4
  parsing is needed.
* Hospital General Information contains no duplicate facility IDs, so no
  deduplication is needed.

``facility_id`` is kept as a string throughout. It is a six-character CMS
Certification Number and casting it to an integer would discard leading zeros.
"""

import logging
import re
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

# CMS marks suppressed or inapplicable measures with these strings rather than
# leaving the cell empty, so the files are perfectly rectangular.
NA_VALUES = ["Not Available", "Not Applicable"]

# Every fact file repeats the hospital's address block. Those columns are
# attributes of a hospital, not of a measurement, so they live in
# dim_hospitals alone and are dropped from the facts.
HOSPITAL_ATTRIBUTE_COLUMNS = [
    "facility_name",
    "address",
    "city_town",
    "state",
    "zip_code",
    "county_parish",
    "telephone_number",
]

DATE_COLUMNS = ["start_date", "end_date"]


def to_snake_case(name):
    """Normalize a CMS column header to snake_case.

    "Facility ID" -> "facility_id", "City/Town" -> "city_town",
    "HCAHPS Answer Percent" -> "hcahps_answer_percent".
    """
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", name)
    return cleaned.strip("_").lower()


def _normalize(frame, numeric_columns, drop_hospital_attributes):
    """Apply the cleaning every dataset needs, in a fixed order."""
    frame = frame.rename(columns={c: to_snake_case(c) for c in frame.columns})
    frame = frame.replace(NA_VALUES, pd.NA)

    if drop_hospital_attributes:
        present = [c for c in HOSPITAL_ATTRIBUTE_COLUMNS if c in frame.columns]
        frame = frame.drop(columns=present)

    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in DATE_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")

    if "measure_id" in frame.columns:
        frame["measure_id"] = frame["measure_id"].str.strip().str.upper()

    # Provenance: which pipeline run produced this row. Stored as datetime64
    # like the other date columns so every date in the frame has one dtype.
    frame["load_date"] = pd.Timestamp(date.today())
    return frame


def clean_readmissions(frame):
    """Unplanned Hospital Visits: 30-day readmission and ED-visit measures."""
    return _normalize(
        frame,
        numeric_columns=[
            "denominator",
            "score",
            "lower_estimate",
            "higher_estimate",
            "number_of_patients",
            "number_of_patients_returned",
        ],
        drop_hospital_attributes=True,
    )


def clean_infections(frame):
    """Healthcare Associated Infections: standardised infection ratios."""
    return _normalize(
        frame,
        numeric_columns=["score"],
        drop_hospital_attributes=True,
    )


def clean_patient_experience(frame):
    """HCAHPS: patient survey results."""
    frame = frame.rename(columns={"HCAHPS Measure ID": "Measure ID"})
    return _normalize(
        frame,
        numeric_columns=[
            "patient_survey_star_rating",
            "hcahps_answer_percent",
            "hcahps_linear_mean_value",
            "number_of_completed_surveys",
            "survey_response_rate_percent",
        ],
        drop_hospital_attributes=True,
    )


def clean_hospitals(frame):
    """Hospital General Information: the dimension.

    Hospital attributes are kept here — this is the one file that owns them.
    """
    numeric = ["hospital_overall_rating"] + [
        to_snake_case(c)
        for c in frame.columns
        if c.startswith("Count of") or c.endswith("Group Measure Count")
    ]
    return _normalize(frame, numeric_columns=numeric, drop_hospital_attributes=False)


TRANSFORMERS = {
    "readmissions": clean_readmissions,
    "infections": clean_infections,
    "patient_experience": clean_patient_experience,
    "hospitals": clean_hospitals,
}


def transform(name, path):
    """Read one raw CSV and return it cleaned.

    Everything is read as a string first so that pandas cannot guess a type
    before the CMS null markers have been replaced — a column of mostly
    numbers with one "Not Available" would otherwise silently become object
    dtype with no indication anything went wrong.
    """
    if name not in TRANSFORMERS:
        raise KeyError(f"no transformer for {name!r}; expected one of {sorted(TRANSFORMERS)}")

    frame = pd.read_csv(path, dtype=str, low_memory=False)
    cleaned = TRANSFORMERS[name](frame)
    logger.info("transformed %s: %s rows, %s columns", name, len(cleaned), len(cleaned.columns))
    return cleaned
