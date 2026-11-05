"""Configuration for the HRRP pipeline."""

from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"

METASTORE_ITEM_URL = "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{id}"
REQUEST_TIMEOUT = 30  # in seconds

# Internal name -> CMS dataset ID. The IDs are stable across quarterly
# releases; the download URL is not, so it gets resolved at runtime.
CMS_DATASETS = {
    "readmissions": "632h-zaca",
    "hospitals": "xubh-q36u",
    "infections": "77hc-ibv8",
    "patient_experience": "dgck-syfz",
}
