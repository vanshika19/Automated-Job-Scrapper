#!/usr/bin/env python3
"""Fill Career Page URL + LinkedIn Jobs URL for family office, VC, and PE workbooks."""

from __future__ import annotations

import argparse
from pathlib import Path

from url_enrichment_core import enrich_workbook

ROOT = Path(__file__).resolve().parent

TARGETS: list[dict] = [
    {
        "id": "family",
        "path": ROOT / "family_offices_structured.xlsx",
        "sheet": "Indian Family Office VCs (Complete)",
        "name_col": "Investor Name",
        "location_col": "Investor Location",
        "location_fallback_col": None,
        "query_context": "family office",
    },
    {
        "id": "vc",
        "path": ROOT / "venture_capital_structured.xlsx",
        "sheet": "Sheet1",
        "name_col": "Investor Name",
        "location_col": "HQ",
        "location_fallback_col": None,
        "query_context": "venture capital",
    },
    {
        "id": "pe",
        "path": ROOT / "private_equity_structured.xlsx",
        "sheet": "PE_Investors_1_190",
        "name_col": "Investor Name",
        "location_col": "Location",
        "location_fallback_col": None,
        "query_context": "private equity",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich investor Excel files with career and LinkedIn job URLs.")
    parser.add_argument(
        "--only",
        choices=["family", "vc", "pe", "all"],
        default="all",
        help="Run a single workbook instead of all three.",
    )
    args = parser.parse_args()
    to_run = TARGETS if args.only == "all" else [t for t in TARGETS if t["id"] == args.only]
    if not to_run:
        raise SystemExit(f"No target for --only {args.only!r}")

    for t in to_run:
        p = t["path"]
        if not p.exists():
            print("Skip (file missing):", p, flush=True)
            continue
        print("=== Enriching", p.name, "===", flush=True)
        enrich_workbook(
            p,
            t["sheet"],
            name_col=t["name_col"],
            location_col=t["location_col"],
            location_fallback_col=t["location_fallback_col"],
            query_context=t["query_context"],
        )


if __name__ == "__main__":
    main()
