"""Command-line entry point for the HRRP ingestion pipeline.

This file owns argument parsing and logging configuration and nothing else.
The work lives in src/pipeline.py, which takes plain Python arguments — that
separation is what makes the pipeline testable without a subprocess.

    python main.py                           # all four datasets
    python main.py --dataset readmissions    # one
    python main.py --skip-download           # reuse data/raw/
"""

import argparse
import logging
import sys

from src.config import CMS_DATASETS
from src.pipeline import run


def build_parser():
    parser = argparse.ArgumentParser(description="Download and clean CMS hospital quality data.")
    parser.add_argument(
        "--dataset",
        action="append",
        choices=sorted(CMS_DATASETS),
        help="dataset to process; repeat for several. Default: all four.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="reuse the CSVs already in data/raw/ instead of refetching.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show debug-level logging.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    # Logging is configured by the application, never by a library module.
    # src/ modules only call logging.getLogger(__name__).
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    requested = args.dataset or sorted(CMS_DATASETS)
    results = run(datasets=requested, skip_download=args.skip_download)

    print(f"\n{len(results)} of {len(requested)} datasets completed")
    for name, info in sorted(results.items()):
        print(f"  {name:20} {info['rows']:>9,} rows  ->  {info['path']}")

    # Non-zero exit if anything failed, so a scheduler or CI step notices.
    return 0 if len(results) == len(requested) else 1


if __name__ == "__main__":
    sys.exit(main())
