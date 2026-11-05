"""Load cleaned DataFrames into the Snowflake raw schema.

Credentials come from environment variables, loaded from a gitignored .env.
Nothing in this module holds a secret, so the file is safe to publish.

One non-obvious detail drives most of this module: Snowflake folds unquoted
identifiers to UPPERCASE. ``sql/02_raw_tables.sql`` creates columns unquoted,
so ``facility_id`` is stored as ``FACILITY_ID``. ``write_pandas`` quotes
identifiers by default, which would make it look for a lowercase
``"facility_id"`` that does not exist. Passing ``quote_identifiers=False``
lets Snowflake apply the same folding to both sides so they match.
"""

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from snowflake.connector import connect
from snowflake.connector.pandas_tools import write_pandas

from src.config import CLEANED_DATA_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)

REQUIRED_VARIABLES = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
]


def connection_settings():
    """Read Snowflake settings from the environment.

    Fails loudly and names every missing variable at once, rather than letting
    the connector raise an opaque authentication error several steps later.
    """
    load_dotenv(PROJECT_ROOT / ".env")

    missing = [name for name in REQUIRED_VARIABLES if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            "missing environment variable(s): "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill it in."
        )

    return {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "role": os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": os.environ["SNOWFLAKE_SCHEMA"],
    }


def get_connection():
    """Open a Snowflake connection. Caller is responsible for closing it."""
    settings = connection_settings()
    logger.info(
        "connecting to %s as %s (%s.%s)",
        settings["account"],
        settings["user"],
        settings["database"],
        settings["schema"],
    )
    return connect(**settings)


def _prepare_for_snowflake(frame):
    """Adapt pandas dtypes to what write_pandas can actually stage.

    write_pandas stages the frame as Parquet, where a pandas datetime64[ns]
    column is written as int64 nanoseconds. Snowflake's COPY then reads it as
    a NUMBER and rejects it against a DATE or TIMESTAMP column:

        Expression type does not match column data type,
        expecting TIMESTAMP_NTZ(9) but got NUMBER(38,0) for column START_DATE

    Converting to Python date objects first makes the Parquet column a real
    date, which COPY accepts. This lives in the loading layer rather than the
    transformer because it is a warehouse serialisation concern, not a
    statement about the right dtype for analysis.
    """
    frame = frame.copy()
    for column in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = frame[column].dt.date
    return frame


def load_dataframe(connection, frame, table):
    """Replace one raw table's contents with `frame`. Returns the row count.

    overwrite=True truncates before inserting, which makes a re-run idempotent:
    running the pipeline twice leaves one copy of the data, not two.
    """
    frame = _prepare_for_snowflake(frame)
    success, chunks, rows, _ = write_pandas(
        connection,
        frame,
        table_name=table.upper(),
        overwrite=True,
        quote_identifiers=False,
        auto_create_table=False,
    )
    if not success:
        raise RuntimeError(f"write_pandas reported failure loading {table}")

    logger.info("loaded %s: %s rows in %s chunk(s)", table, f"{rows:,}", chunks)
    return rows


def load_all(cleaned_dir=CLEANED_DATA_DIR, connection=None):
    """Load every Parquet file in `cleaned_dir`. Returns {table: row_count}.

    The table name is the Parquet file's stem, which is the internal dataset
    key — the same name used for the raw CSV and for the table in
    sql/02_raw_tables.sql. One name flows through the whole pipeline.
    """
    parquet_files = sorted(Path(cleaned_dir).glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"no Parquet files in {cleaned_dir}; run `python main.py` first"
        )

    own_connection = connection is None
    connection = connection or get_connection()
    results = {}

    try:
        for path in parquet_files:
            frame = pd.read_parquet(path)
            try:
                results[path.stem] = load_dataframe(connection, frame, path.stem)
            except Exception:
                logger.exception("failed to load %s", path.stem)
    finally:
        if own_connection:
            connection.close()

    return results


def verify(connection=None):
    """Report row counts straight from Snowflake, not from what we think we sent.

    A load that reports success and a table that actually holds the rows are
    two different claims. This checks the second one.
    """
    own_connection = connection is None
    connection = connection or get_connection()
    counts = {}

    try:
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES IN SCHEMA raw")
        tables = [row[1] for row in cursor.fetchall()]

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM raw.{table}")
            counts[table.lower()] = cursor.fetchone()[0]
    finally:
        if own_connection:
            connection.close()

    return counts
