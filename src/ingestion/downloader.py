"""Download CMS provider datasets to the raw data directory.

CMS publishes direct CSV download links, so this layer uses plain HTTP rather
than browser automation. The download URL is not stable across quarterly
releases, so every run resolves it from the metastore API first.
"""

import logging
from pathlib import Path

import requests

from src.config import (
    CMS_DATASETS,
    METASTORE_ITEM_URL,
    RAW_DATA_DIR,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192


def resolve_download_url(dataset_id):
    """Return the current CSV download URL for a CMS dataset ID.

    The URL carries a content hash and version stamp that change with each
    quarterly release, so it is resolved from the metastore at runtime
    rather than hardcoded.
    """
    response = requests.get(
        METASTORE_ITEM_URL.format(id=dataset_id),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["distribution"][0]["downloadURL"]


def download(name, dest_dir=RAW_DATA_DIR):
    """Download one CMS dataset. Returns the path written.

    `name` is an internal key from CMS_DATASETS, not a CMS title. The output
    filename follows that key so downstream stages have a stable name to look
    for regardless of how CMS renames their files.
    """
    if name not in CMS_DATASETS:
        raise KeyError(f"unknown dataset {name!r}; expected one of {sorted(CMS_DATASETS)}")

    url = resolve_download_url(CMS_DATASETS[name])
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = dest_dir / f"{name}.csv"

    # Write to a temp name and rename on success. A rename is atomic, so an
    # interrupted download can never leave a truncated file sitting at the
    # real path looking complete.
    partial = destination.with_suffix(".csv.partial")

    logger.info("downloading %s", name)
    with requests.get(url, timeout=REQUEST_TIMEOUT, stream=True) as response:
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "csv" not in content_type and "octet-stream" not in content_type:
            raise ValueError(
                f"{name}: expected a CSV, got Content-Type {content_type!r}"
            )

        # stream=True plus iter_content keeps memory flat regardless of file
        # size. HCAHPS alone is over 100 MB.
        with open(partial, "wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                handle.write(chunk)

    if partial.stat().st_size == 0:
        partial.unlink()
        raise ValueError(f"{name}: downloaded file was empty")

    partial.replace(destination)
    logger.info("wrote %s (%.1f MB)", destination.name, destination.stat().st_size / 1e6)
    return destination


def download_all(names=None, dest_dir=RAW_DATA_DIR):
    """Download several datasets. Returns {name: path} for those that succeeded.

    One dataset failing does not stop the others — a CMS outage on one endpoint
    should not cost the whole run. Failures are logged and omitted from the
    result, so the caller can see what is missing by comparing keys.
    """
    names = names or list(CMS_DATASETS)
    results = {}

    for name in names:
        try:
            results[name] = download(name, dest_dir=dest_dir)
        except Exception:
            logger.exception("failed to download %s", name)

    return results
