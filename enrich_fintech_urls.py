#!/usr/bin/env python3
"""Fill / re-verify Career Page URL + LinkedIn Jobs URL on the fintech workbook.

Default behaviour (no flags) is the historical one: skip rows that already
have both URLs filled.

    python enrich_fintech_urls.py                # fill missing only
    python enrich_fintech_urls.py --reverify     # re-check every existing URL,
                                                 # replace ones that fail
                                                 # (aggregator / wrong domain /
                                                 #  dead link / no career
                                                 #  signals).
    python enrich_fintech_urls.py --only-segment "BFSI FinTech list 2025"
                                                 # only that Sub-Segment; blanks
                                                 # only; other rows untouched.
    # Prefer applying ``fintech_careers.csv`` first (no network):
    #   python bfsi_career_csv.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

from url_enrichment_core import enrich_workbook

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--reverify",
        action="store_true",
        help="Re-check every existing Career Page URL; replace ones that fail verification.",
    )
    p.add_argument(
        "--only-segment",
        metavar="VALUE",
        default=None,
        help=(
            "Only process rows whose Sub-Segment (see --segment-column) equals this "
            "value; fill blank Career / LinkedIn cells only; never overwrite or touch "
            "other rows. Implies no reverify."
        ),
    )
    p.add_argument(
        "--segment-column",
        default="Sub-Segment",
        help="Column to match against --only-segment (default: %(default)r).",
    )
    p.add_argument(
        "--xlsx",
        default=str(ROOT / "fintech_companies_structured.xlsx"),
        help="Workbook path (default: %(default)s).",
    )
    p.add_argument(
        "--sheet",
        default="Fintech Companies",
        help="Sheet name (default: %(default)r).",
    )
    args = p.parse_args(argv)

    enrich_workbook(
        args.xlsx,
        args.sheet,
        name_col="Company Name",
        location_col="Country",
        location_fallback_col="Region",
        query_context="",
        reverify=args.reverify,
        segment_filter=args.only_segment,
        segment_col=args.segment_column,
    )


if __name__ == "__main__":
    main()
