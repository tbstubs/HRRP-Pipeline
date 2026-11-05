"""Tests for the cleaning layer.

These run against a small committed fixture, never against data/raw/. The
fixture is hand-made and carries the edge cases measured in the real CMS
files: both null markers, a leading-zero facility ID, and a measure ID with
stray whitespace and wrong casing.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.transformer import (
    HOSPITAL_ATTRIBUTE_COLUMNS,
    to_snake_case,
    transform,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "readmissions_sample.csv"


@pytest.fixture
def readmissions():
    return transform("readmissions", FIXTURE)


class TestToSnakeCase:
    @pytest.mark.parametrize(
        "header,expected",
        [
            ("Facility ID", "facility_id"),
            ("City/Town", "city_town"),
            ("HCAHPS Answer Percent", "hcahps_answer_percent"),
            ("Number of Patients Returned", "number_of_patients_returned"),
            ("Compared to National", "compared_to_national"),
        ],
    )
    def test_normalizes_headers(self, header, expected):
        assert to_snake_case(header) == expected


class TestNullHandling:
    def test_both_cms_null_markers_become_na(self, readmissions):
        """CMS uses 'Not Available' AND 'Not Applicable'. Both must be null."""
        assert readmissions["score"].isna().sum() == 2

    def test_surviving_values_are_numeric(self, readmissions):
        assert pd.api.types.is_numeric_dtype(readmissions["score"])
        assert readmissions["score"].dropna().tolist() == [21.4, 22.8]

    def test_null_markers_do_not_leak_as_strings(self, readmissions):
        flattened = readmissions.astype(str).to_numpy().ravel()
        assert "Not Available" not in flattened
        assert "Not Applicable" not in flattened


class TestFacilityId:
    def test_stays_a_string(self, readmissions):
        """facility_id is a six-character CCN, not a number."""
        assert readmissions["facility_id"].dtype == object

    def test_leading_zeros_survive(self, readmissions):
        assert readmissions["facility_id"].iloc[0] == "010001"


class TestStarSchemaShape:
    def test_hospital_attributes_dropped_from_facts(self, readmissions):
        """Address and name belong to dim_hospitals, not to a measurement."""
        for column in HOSPITAL_ATTRIBUTE_COLUMNS:
            assert column not in readmissions.columns

    def test_join_key_and_measure_key_survive(self, readmissions):
        assert "facility_id" in readmissions.columns
        assert "measure_id" in readmissions.columns


class TestMeasureId:
    def test_whitespace_and_case_normalized(self, readmissions):
        """A stray ' readm_30_ami ' must match READM_30_AMI from another file."""
        assert "READM_30_AMI" in set(readmissions["measure_id"])


class TestProvenance:
    def test_load_date_is_today(self, readmissions):
        assert (readmissions["load_date"].dt.date == date.today()).all()

    def test_every_date_column_shares_one_dtype(self, readmissions):
        """The loader converts datetime64 wholesale, so a stray object column
        of dates would be staged as a string and silently typed wrong."""
        for column in ("start_date", "end_date", "load_date"):
            assert pd.api.types.is_datetime64_any_dtype(readmissions[column]), column


class TestDispatch:
    def test_unknown_dataset_raises(self):
        with pytest.raises(KeyError, match="no transformer"):
            transform("not_a_dataset", FIXTURE)

    def test_row_count_preserved(self, readmissions):
        """Cleaning must not silently drop rows; suppression is a null, not a delete."""
        assert len(readmissions) == 4
