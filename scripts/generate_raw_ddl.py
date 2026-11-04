"""Generate sql/02_raw_tables.sql from the cleaned Parquet files.

The raw table definitions are derived from the transformer's actual output
rather than written by hand. Hand-written DDL for 39 columns drifts the first
time a column is added, and the failure is silent until a load errors on a
column that does not exist.

Run after the pipeline has produced data/cleaned/:

    python -m scripts.generate_raw_ddl
"""

from pathlib import Path

import pandas as pd

from src.config import CLEANED_DATA_DIR, PROJECT_ROOT

OUTPUT_PATH = PROJECT_ROOT / "sql" / "02_raw_tables.sql"

HEADER = """\
-- Raw landing tables for the HRRP pipeline.
-- GENERATED from data/cleaned/*.parquet — do not edit by hand.
-- Regenerate with: python -m scripts.generate_raw_ddl

USE DATABASE healthcare_analytics;
USE SCHEMA raw;
"""


def snowflake_type(dtype):
    """Map a pandas dtype to a Snowflake column type.

    Object columns become VARCHAR rather than anything narrower: facility_id
    is a six-character CMS Certification Number, and a numeric type would
    discard its leading zeros.
    """
    name = str(dtype)
    if name.startswith(("int", "Int")):
        return "NUMBER(38,0)"
    if name.startswith(("float", "Float")):
        return "FLOAT"
    if name.startswith("datetime"):
        # DATE, not TIMESTAMP: every date in this dataset is a measurement
        # period boundary with no time component. The loader converts the
        # pandas datetime64 to a date before writing.
        return "DATE"
    if name == "bool":
        return "BOOLEAN"
    if name == "object":
        return "VARCHAR"
    return "VARCHAR"


def build_ddl(cleaned_dir=CLEANED_DATA_DIR):
    parquet_files = sorted(Path(cleaned_dir).glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"no Parquet files in {cleaned_dir}; run `python main.py` first"
        )

    sections = [HEADER]
    for path in parquet_files:
        frame = pd.read_parquet(path)
        width = max(len(c) for c in frame.columns) + 2
        columns = ",\n".join(
            f"    {column:<{width}} {snowflake_type(dtype)}"
            for column, dtype in frame.dtypes.items()
        )
        sections.append(f"CREATE OR REPLACE TABLE raw.{path.stem} (\n{columns}\n);")

    return "\n\n".join(sections) + "\n"


def main():
    ddl = build_ddl()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(ddl)
    table_count = ddl.count("CREATE OR REPLACE TABLE")
    print(f"wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)} ({table_count} tables)")


if __name__ == "__main__":
    main()
