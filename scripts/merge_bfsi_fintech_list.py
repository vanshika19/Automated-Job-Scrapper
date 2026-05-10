#!/usr/bin/env python3
"""Merge companies from the BFSI & FinTech Industry 2025 annex into the fintech workbook.

Adds only rows whose normalized name is not already present (case/spacing insensitive).
Default location: India / Asia for this list; Sub-Segment notes the source.
Career / LinkedIn URLs are filled from ``fintech_careers.csv`` or
``fintech_career.csv`` in the repo root when present (same normalized name
matching); otherwise left blank.

Usage:
  python scripts/merge_bfsi_fintech_list.py
  python scripts/merge_bfsi_fintech_list.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfsi_career_csv import load_career_lookup, norm_company  # noqa: E402
XLSX = ROOT / "fintech_companies_structured.xlsx"
SHEET = "Fintech Companies"

# Extracted names from "List of Leading FinTech Companies" (annex 2025).
# OCR fixes: fi n→fin, fl o→flo, Kaleidofi n→Kaleidofin, Livfi n→LivFin, Modefi n→Modefin,
# Stashfi n→Stashfin, Veefi n→Veefin, Wishfi n→Wishfin.
BFSI_NAMES: tuple[str, ...] = (
    "1Crowd",
    "5paisa Capital",
    "ACKO",
    "Advarisk",
    "Advisorymandi.com",
    "Affordplan",
    "Agrim",
    "Agrosperity Tech Solutions",
    "Arthmate",
    "Ascend Capital",
    "AssetPlus",
    "Assurekit",
    "Autovert",
    "Auxilo",
    "Avanti",
    "Basic Home Loan",
    "BharatPe",
    "Bimaplan",
    "BonusHub",
    "Card91",
    "CASHe",
    "Cashflo",
    "Chqbook",
    "Clix Capital",
    "CRED",
    "CredAble",
    "Credgenics",
    "Credilio",
    "Credit Fair",
    "CreditNirvana",
    "CrediWatch",
    "Credochain",
    "CredRight",
    "Credy",
    "Cube Wealth",
    "Davinta",
    "Decentro",
    "Dezerv",
    "DGV",
    "Digio",
    "Digit Insurance",
    "Drona Pay",
    "Ecofy",
    "Eduvanz",
    "EHFL",
    "Enterprise Tiger",
    "ePayLater",
    "Esthenos",
    "EximPe",
    "FamApp",
    "Fello",
    "Fi",
    "Fibe",
    "FidyPay",
    "FinAGG",
    "Finbingo",
    "FinBit",
    "FinBox",
    "FingPay",
    "Finity",
    "Finnable",
    "Finzy",
    "Fisdom",
    "FlexiLoans",
    "Flexmoney",
    "Freo",
    "Ftcash",
    "GetVantage",
    "GramCover",
    "GrayQuest",
    "Grip",
    "GroMo",
    "Groww",
    "GyanDhan",
    "Happy Loans",
    "HomeCapital",
    "IDfy",
    "InCred",
    "indiagold",
    "IndiaLends",
    "Indifi",
    "INDmoney",
    "InsuranceDekho",
    "InvestorAi",
    "Jai Kisan",
    "Jama Wealth",
    "Jar",
    "Jodo",
    "Jupiter",
    "Kaleidofin",
    "KapitalTech",
    "Kinara Capital",
    "Kissht",
    "Kiwi",
    "KNAB Finance",
    "Kosh",
    "KreditBee",
    "KredX",
    "Kuvera",
    "Lazypay",
    "LendenClub",
    "Lendingkart",
    "Lentra",
    "LEO 1",
    "LiquiLoans",
    "LivFin",
    "Loan Frame",
    "LoanTap",
    "M1xchange",
    "M2P",
    "MarketsMojo",
    "MarketWolf",
    "Minko",
    "Mintifi",
    "Mintoak",
    "Modefin",
    "Monedo",
    "Money View",
    "MoneyTap",
    "mPokket",
    "MyLoanCare",
    "MyShubhLife",
    "Namaste Credit",
    "Navi",
    "NeoGrowth",
    "New Street Tech",
    "New Street Technologies",
    "NIRA",
    "Nira Finance",
    "Niro",
    "Niyo",
    "Niyogin",
    "Nova Benefits",
    "NPST",
    "OLA Money",
    "Olyv",
    "Onebanc",
    "OneCard",
    "Onemoney",
    "OneStack",
    "OnSurity",
    "Open",
    "Oro Money",
    "Orocorp Technologies",
    "OTO",
    "Oxyzo",
    "PayGlocal",
    "PayMeIndia",
    "PayNearby",
    "PayPhi",
    "Paytm Money",
    "Paz Care",
    "Phocket",
    "Plum",
    "Progcap",
    "Propelld",
    "PropertyShare",
    "psbloansin59minutes.com",
    "QuickInsure",
    "Raise",
    "Razorpay",
    "RenewBuy",
    "RevFin",
    "Riskcovry",
    "Rupeek",
    "RupeeRedee",
    "Rupifi",
    "SabPaisa",
    "SafexPay",
    "Scoreme",
    "Scripbox",
    "SecureNow",
    "SETU",
    "ShopSe",
    "Signzy",
    "Simpl",
    "Siply",
    "slice",
    "smallcase",
    "Snapmint",
    "Stable Money",
    "Stashfin",
    "Strata",
    "SuperMoney",
    "Symbo",
    "Symbo Insurance",
    "Synaptic",
    "TCPL",
    "Toffee",
    "ToneTag",
    "Trustt",
    "Turtlemint",
    "TWID",
    "UBFC",
    "Uni Cards",
    "Unnati",
    "Upswing",
    "Veefin",
    "VegaPay",
    "Velocity",
    "Vested Finance",
    "Vitraya",
    "Vivifi India Finance",
    "Vivriti Capital",
    "WealthDesk",
    "Wealthy",
    "WeRize",
    "Wint Wealth",
    "Wishfin",
    "WonderLend Hubs",
)


def _display_name(raw: str) -> str:
    """Light titling for known odd cases."""
    if raw in ("CRED", "INDmoney", "OLA Money", "SETU", "TWID", "UBFC", "OTO", "EHFL", "NPST"):
        return raw
    if raw == "indiagold":
        return "indiagold"
    if raw == "Fi":
        return "Fi"
    if raw == "slice":
        return "slice"
    if raw == "smallcase":
        return "smallcase"
    return raw


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    df = pd.read_excel(XLSX, sheet_name=SHEET)
    existing = {norm_company(str(x)) for x in df["Company Name"].dropna()}
    career_lookup = load_career_lookup(ROOT)

    additions: list[dict] = []
    for raw in BFSI_NAMES:
        name = _display_name(raw)
        key = norm_company(name)
        if not key:
            continue
        if key in existing:
            continue
        existing.add(key)
        career, li = career_lookup.get(key, ("", ""))
        additions.append(
            {
                "Company Name": name,
                "Country": "India",
                "Region": "Asia",
                "Sub-Segment": "BFSI FinTech list 2025",
                "Career Page URL": career,
                "LinkedIn Jobs URL": li,
            }
        )

    print(f"Existing rows: {len(df)}")
    print(f"Canonical list: {len(BFSI_NAMES)}")
    print(f"New rows to add: {len(additions)}")
    if additions and args.dry_run:
        for r in additions[:25]:
            print("  +", r["Company Name"])
        if len(additions) > 25:
            print("  ...")
        return

    if not additions:
        print("Nothing to merge.")
        return

    extra = pd.DataFrame(additions)
    out = pd.concat([df, extra], ignore_index=True)
    out.to_excel(XLSX, sheet_name=SHEET, index=False)
    print(f"Saved {len(out)} rows -> {XLSX}")


if __name__ == "__main__":
    main()
