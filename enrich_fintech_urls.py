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
    )


if __name__ == "__main__":
    main()
