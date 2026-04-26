"""Load companies from the existing structured Excel workbooks."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .models import Company

NAME_COLS = ("Company Name", "Investor Name")
LOCATION_COLS = ("Country", "HQ", "Location", "Investor Location", "Region")
SEGMENT_COLS = ("Sub-Segment", "Investor Type", "Type", "Sectors of Investment")

DEFAULT_REGISTRIES: tuple[tuple[str, str, str], ...] = (
    ("fintech_companies_structured.xlsx", "Fintech Companies", "Fintech"),
    ("family_offices_structured.xlsx", "Indian Family Office VCs (Complete)", "Family Office"),
    ("venture_capital_structured.xlsx", "Sheet1", "Venture Capital"),
    ("private_equity_structured.xlsx", "PE_Investors_1_190", "Private Equity"),
)


def _first_present(row: pd.Series, cols: Iterable[str]) -> str:
    for c in cols:
        if c in row.index:
            v = row[c]
            if pd.notna(v) and str(v).strip():
                return str(v).strip()
    return ""


def load_workbook(path: str | Path, sheet: str, segment: str = "") -> list[Company]:
    df = pd.read_excel(path, sheet_name=sheet)
    out: list[Company] = []
    for _, row in df.iterrows():
        name = _first_present(row, NAME_COLS)
        if not name:
            continue
        out.append(
            Company(
                name=name,
                careers_url=_first_present(row, ("Career Page URL",)),
                linkedin_url=_first_present(row, ("LinkedIn Jobs URL",)),
                country=_first_present(row, LOCATION_COLS),
                segment=segment or _first_present(row, SEGMENT_COLS),
            )
        )
    return out


def load_all(root: str | Path | None = None) -> list[Company]:
    base = Path(root) if root else Path(__file__).resolve().parent.parent
    companies: list[Company] = []
    for fname, sheet, segment in DEFAULT_REGISTRIES:
        path = base / fname
        if path.exists():
            companies.extend(load_workbook(path, sheet, segment))
    return companies
