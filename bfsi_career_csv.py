#!/usr/bin/env python3
"""Map pre-collected BFSI career / LinkedIn URLs from CSV into the fintech workbook.

Looks for ``fintech_careers.csv`` or ``fintech_career.csv`` in the repo root (first
match wins). Only rows in the given Sub-Segment are updated, and only **blank**
URL cells are filled (existing values are never overwritten).

Usage:
  python bfsi_career_csv.py
  python bfsi_career_csv.py --dry-run
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULT_SHEET = "Fintech Companies"
DEFAULT_SEGMENT = "BFSI FinTech list 2025"


def norm_company(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def career_csv_candidates(root: Path | None = None) -> list[Path]:
    base = root or ROOT
    return [base / "fintech_careers.csv", base / "fintech_career.csv"]


def load_career_lookup(root: Path | None = None) -> dict[str, tuple[str, str]]:
    """Normalized company name -> (career_url, linkedin_url). Empty if no CSV found."""
    base = root or ROOT
    path = next((p for p in career_csv_candidates(base) if p.is_file()), None)
    if path is None:
        return {}
    return _read_csv_lookup(path)


def _read_csv_lookup(path: Path) -> dict[str, tuple[str, str]]:
    df = pd.read_csv(path)
    if "Company" not in df.columns:
        raise KeyError(f"{path}: expected a 'Company' column")

    def col(*names: str) -> str | None:
        low = {c.strip().lower(): c for c in df.columns}
        for n in names:
            if n.lower() in low:
                return low[n.lower()]
        return None

    c_company = col("company")
    c_career = col("career page", "career", "career page url")
    c_li = col("linkedin", "linkedin jobs", "linkedin jobs url")
    if not c_career:
        c_career = "Career Page" if "Career Page" in df.columns else None
    if not c_li:
        c_li = "LinkedIn" if "LinkedIn" in df.columns else None

    out: dict[str, tuple[str, str]] = {}
    company_col = c_company or "Company"
    for _, row in df.iterrows():
        raw = row.get(company_col)
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            continue
        key = norm_company(str(raw))
        if not key:
            continue

        def cell(url_col: str | None) -> str:
            if not url_col or url_col not in df.columns:
                return ""
            v = row.get(url_col)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return ""
            s = str(v).strip()
            return "" if s.lower() == "nan" else s

        career = cell(c_career)
        li = cell(c_li)
        out[key] = (career, li)

    return out


def apply_csv_to_workbook(
    xlsx: Path | str,
    sheet: str,
    *,
    segment: str = DEFAULT_SEGMENT,
    segment_col: str = "Sub-Segment",
    name_col: str = "Company Name",
    root: Path | None = None,
    dry_run: bool = False,
) -> None:
    path = Path(xlsx)
    lookup = load_career_lookup(root)
    if not lookup:
        searched = ", ".join(str(p.name) for p in career_csv_candidates(root))
        raise FileNotFoundError(
            f"No career CSV found under {root or ROOT}; tried: {searched}"
        )

    df = pd.read_excel(path, sheet_name=sheet)
    if name_col not in df.columns:
        raise KeyError(f"Missing {name_col!r} in {path}")
    if segment_col not in df.columns:
        raise KeyError(f"Missing {segment_col!r} in {path}")

    for col in ("Career Page URL", "LinkedIn Jobs URL"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).replace("nan", "")

    want = segment.strip()
    filled_c = filled_li = 0
    bfsi_rows = no_csv = 0

    for i, row in df.iterrows():
        if str(row.get(segment_col, "") or "").strip() != want:
            continue
        bfsi_rows += 1
        name = str(row.get(name_col, "") or "").strip()
        if not name:
            continue
        key = norm_company(name)
        pair = lookup.get(key)
        if not pair:
            no_csv += 1
            continue
        career, li = pair
        ec = str(row.get("Career Page URL", "") or "").strip()
        el = str(row.get("LinkedIn Jobs URL", "") or "").strip()

        if not ec and career:
            df.at[i, "Career Page URL"] = career
            filled_c += 1
        if not el and li:
            df.at[i, "LinkedIn Jobs URL"] = li
            filled_li += 1

    print(
        f"CSV: {len(lookup)} company key(s) | BFSI rows: {bfsi_rows} | "
        f"filled Career: {filled_c}, LinkedIn: {filled_li} | no CSV match: {no_csv}",
        flush=True,
    )

    if dry_run:
        print("Dry-run: workbook not written.", flush=True)
        return

    df.to_excel(path, sheet_name=sheet, index=False)
    print(f"Saved {path}", flush=True)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--xlsx",
        default=str(ROOT / "fintech_companies_structured.xlsx"),
        help="Workbook path (default: %(default)s).",
    )
    p.add_argument("--sheet", default=DEFAULT_SHEET, help="Sheet name.")
    p.add_argument(
        "--segment",
        default=DEFAULT_SEGMENT,
        help="Sub-Segment value to restrict updates (default: %(default)r).",
    )
    p.add_argument("--segment-column", default="Sub-Segment")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    apply_csv_to_workbook(
        args.xlsx,
        args.sheet,
        segment=args.segment,
        segment_col=args.segment_column,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
