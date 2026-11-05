"""Orchestrate the ingestion pipeline: download, transform, save.

This module is deliberately free of any command-line handling. It takes
ordinary Python arguments and returns ordinary Python values, so it can be
called from a test, a notebook, or a scheduler as easily as from the CLI in
main.py.
"""

import logging
from pathlib import Path

from src.config import CLEANED_DATA_DIR, CMS_DATASETS, RAW_DATA_DIR
from src.ingestion import downloader, transformer

logger = logging.getLogger(__name__)


def run(datasets=None, raw_dir=RAW_DATA_DIR, cleaned_dir=CLEANED_DATA_DIR, skip_download=False):
    """Run the pipeline. Returns {name: {"rows": int, "path": Path}}.

    A dataset that fails is logged and omitted from the result rather than
    aborting the run — the caller can see what is missing by comparing the
    returned keys against the requested names.

    `skip_download` reuses whatever is already in raw_dir. Useful while
    developing the transformer, since re-downloading HCAHPS is 100 MB.
    """
    names = datasets or list(CMS_DATASETS)
    unknown = set(names) - set(CMS_DATASETS)
    if unknown:
        raise KeyError(f"unknown dataset(s) {sorted(unknown)}; expected {sorted(CMS_DATASETS)}")

    cleaned_dir = Path(cleaned_dir)
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for name in names:
        try:
            if skip_download:
                raw_path = Path(raw_dir) / f"{name}.csv"
                if not raw_path.exists():
                    raise FileNotFoundError(f"{raw_path} not present; run without --skip-download")
            else:
                raw_path = downloader.download(name, dest_dir=raw_dir)

            frame = transformer.transform(name, raw_path)

            # Parquet rather than CSV: it preserves the dtypes this layer just
            # established, so the Snowflake loader does not have to re-infer
            # them and cannot disagree with the transformer.
            out_path = cleaned_dir / f"{name}.parquet"
            frame.to_parquet(out_path, index=False)

            results[name] = {"rows": len(frame), "path": out_path}
            logger.info("saved %s (%s rows)", out_path.name, f"{len(frame):,}")
        except Exception:
            logger.exception("pipeline failed for %s", name)

    missing = set(names) - set(results)
    if missing:
        logger.warning("completed with failures: %s", sorted(missing))

    return results
