#!/usr/bin/env python3
"""Fill Career Page URL and LinkedIn Jobs URL in fintech_companies_structured.xlsx using DDGS."""

from __future__ import annotations

from pathlib import Path

from url_enrichment_core import enrich_workbook

ROOT = Path(__file__).resolve().parent


def main() -> None:
    enrich_workbook(
        ROOT / "fintech_companies_structured.xlsx",
        "Fintech Companies",
        name_col="Company Name",
        location_col="Country",
        location_fallback_col="Region",
        query_context="",
    )


if __name__ == "__main__":
    main()
