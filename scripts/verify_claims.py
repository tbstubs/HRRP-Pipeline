"""Verify the ten claims this project exists to make true.

The resume describes this pipeline in specific terms. This script checks each
of those statements against the repository and the live warehouse rather than
against anybody's memory of what was built.

    python -m scripts.verify_claims

Claim 10 cannot be checked from here -- a .pbix is a binary built on a Windows
VM -- so it is reported as requiring manual confirmation rather than silently
passing.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.config import CMS_DATASETS, PROJECT_ROOT

DBT_DIR = PROJECT_ROOT / "dbt_project"
MANIFEST = DBT_DIR / "target" / "manifest.json"

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def check(label, passed, detail=""):
    mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{mark}] {label}")
    if detail:
        print(f"         {detail}")
    return bool(passed)


def manual(label, detail):
    print(f"  [{YELLOW}MANUAL{RESET}] {label}")
    print(f"           {detail}")


def warehouse_tables(schema):
    """Table names in a Snowflake schema, lowercased."""
    from snowflake.connector import connect

    load_dotenv(PROJECT_ROOT / ".env")
    conn = connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
    )
    try:
        cur = conn.cursor()
        cur.execute(f"SHOW TABLES IN SCHEMA {schema}")
        names = [r[1].lower() for r in cur.fetchall()]
        columns = {}
        for name in names:
            cur.execute(f"DESC TABLE {schema}.{name}")
            columns[name] = [r[0].lower() for r in cur.fetchall()]
        return names, columns
    finally:
        conn.close()


def main():
    print("\nHRRP — verifying the ten claims\n")
    results = []

    # 1 — four CMS datasets
    raw_tables, _ = warehouse_tables("raw")
    results.append(check(
        "1. Four CMS datasets ingested",
        len(CMS_DATASETS) == 4 and len(raw_tables) == 4,
        f"{len(CMS_DATASETS)} configured, {len(raw_tables)} raw tables: {sorted(raw_tables)}",
    ))

    # 2 — Python and Pandas
    transformer = (PROJECT_ROOT / "src" / "ingestion" / "transformer.py").read_text()
    results.append(check(
        "2. Python and Pandas as the ingestion layer",
        "import pandas" in transformer,
        "src/ingestion/transformer.py imports pandas",
    ))

    # 3 — Snowflake
    results.append(check(
        "3. Snowflake as the warehouse",
        len(raw_tables) > 0,
        f"connected to {os.environ['SNOWFLAKE_DATABASE']}",
    ))

    # 4 — dbt
    results.append(check(
        "4. dbt as the transformation layer",
        MANIFEST.exists(),
        "dbt_project/target/manifest.json present",
    ))

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"nodes": {}}
    models = {k.split(".")[-1] for k, v in manifest["nodes"].items() if v["resource_type"] == "model"}

    mart_tables, mart_columns = warehouse_tables("marts")
    facts = sorted(t for t in mart_tables if t.startswith("fct_"))
    dims = sorted(t for t in mart_tables if t.startswith("dim_"))

    # 5 — galaxy schema with dim_hospitals
    results.append(check(
        "5. Galaxy schema with a dimension named dim_hospitals",
        "dim_hospitals" in mart_tables and len(dims) >= 2 and len(facts) >= 2,
        f"dimensions {dims}; several facts share them, which is a galaxy",
    ))

    # 6 — four fact tables, all on facility_id
    keyed = [f for f in facts if "facility_id" in mart_columns[f]]
    results.append(check(
        "6. Four fact tables, all keyed on facility_id",
        len(facts) == 4 and len(keyed) == 4,
        f"{facts}",
    ))

    # 7 — sliceable across condition, geography, benchmark tier
    axes = {
        "condition": "clinical_condition" in mart_columns.get("dim_measures", []),
        "geography": "state" in mart_columns.get("dim_hospitals", []),
        "benchmark tier": "benchmark_tier" in mart_columns.get("fct_hospital_quality", []),
    }
    results.append(check(
        "7. Sliceable across condition, geography and benchmark tier",
        all(axes.values()),
        ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in axes.items()),
    ))

    # 8 — all five test types
    tests = [v for v in manifest["nodes"].values() if v["resource_type"] == "test"]
    kinds = {"not_null": 0, "unique": 0, "accepted_values": 0, "relationships": 0, "custom bounds": 0}
    for t in tests:
        name = t["name"]
        if name.startswith("not_null"):
            kinds["not_null"] += 1
        elif name.startswith("unique"):
            kinds["unique"] += 1
        elif name.startswith("accepted_values"):
            kinds["accepted_values"] += 1
        elif name.startswith("relationships"):
            kinds["relationships"] += 1
        elif t.get("test_metadata") is None:
            kinds["custom bounds"] += 1
    results.append(check(
        "8. dbt tests covering all five types",
        all(v > 0 for v in kinds.values()),
        ", ".join(f"{k}={v}" for k, v in kinds.items()) + f"  ({len(tests)} total)",
    ))

    # 9 — dbt docs
    docs = DBT_DIR / "target" / "index.html"
    catalog = DBT_DIR / "target" / "catalog.json"
    results.append(check(
        "9. dbt docs generating documentation",
        docs.exists() and catalog.exists(),
        f"index.html {docs.stat().st_size // 1024} KB, catalog.json present" if docs.exists() else "not generated",
    ))

    # 10 — Power BI, not checkable from here
    manual(
        "10. Four-page Power BI dashboard",
        "A .pbix is a binary built on a Windows VM. Confirm by opening it and "
        "counting pages; it is not asserted by this script.",
    )

    print(f"\n  {sum(results)} of 9 automatable claims verified; 1 requires manual confirmation.\n")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
