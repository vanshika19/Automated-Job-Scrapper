#!/usr/bin/env python3
"""Apply hand-verified Career Page URL / LinkedIn fixes for the fintech workbook.

Run after automated enrichment / reverify to correct wrong-host matches (aggregators,
similar brand names, rebrands).  See logs/reverify_fintech.log for the 2026-04 pass.

    python patch_fintech_urls.py
"""

from __future__ import annotations

import pandas as pd

XLSX = "fintech_companies_structured.xlsx"
SHEET = "Fintech Companies"

PATCHES: dict[str, dict[str, str]] = {
    # --- Existing curated rows (deduped / corrected) ---------------------------
    "Ramp": {
        "Career Page URL": "https://ramp.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/ramp/jobs/",
    },
    "Finverity": {
        "Career Page URL": "https://www.finverity.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/finverity/jobs/",
    },
    "Modern Treasury": {
        "Career Page URL": "https://www.moderntreasury.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/modern-treasury/jobs/",
    },
    "Satispay": {
        "Career Page URL": "https://www.satispay.com/en-it/work-at-satispay/open-positions/",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/satispay/jobs/",
    },
    "Open": {
        "Career Page URL": "https://open.money/career",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/bankwithopen/jobs/",
    },
    "Clear": {
        "Career Page URL": "https://cleartax.in/s/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/cleartax/jobs/",
    },
    "Nium": {
        "Career Page URL": "https://nium.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/nium-global/jobs/",
    },
    "Mercury": {
        "Career Page URL": "https://mercury.com/jobs",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/mercuryhq/jobs/",
    },
    "Square (Block)": {
        "Career Page URL": "https://block.xyz/careers/jobs",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/joinblock/jobs/",
    },
    "Jupiter": {
        "Career Page URL": "https://jupiter.money/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/jupiter-money/jobs/",
    },
    "Column": {
        "Career Page URL": "https://www.column.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/column-bank/jobs/",
    },
    "Unit": {
        "Career Page URL": "https://www.unit.co/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/unit-finance/jobs/",
    },
    "Current": {
        "Career Page URL": "https://current.com/careers/",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/current/jobs/",
    },
    "Synapse": {
        "Career Page URL": "https://synapsefi.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/synapsepay/jobs/",
    },
    "Stripe": {"Career Page URL": "https://stripe.com/jobs"},
    "Plaid": {"Career Page URL": "https://plaid.com/careers"},
    # Chime (US neobank) — not chimeplc / stadium SoFi
    "Chime": {"Career Page URL": "https://www.chime.com/careers/"},
    "SoFi": {"Career Page URL": "https://www.sofi.com/careers"},
    "Lithic": {"Career Page URL": "https://job-boards.greenhouse.io/lithic"},
    "Apex Fintech": {
        "Career Page URL": "https://apexfintechsolutions.com/about/culture-careers/open-positions/",
    },
    "Betterment": {"Career Page URL": "https://www.betterment.com/careers/current-openings"},
    "Wise": {"Career Page URL": "https://wise.com/jobs"},
    "Scalable Capital": {"Career Page URL": "https://scalable.capital/en/careers"},
    "Tink": {"Career Page URL": "https://tink.com/careers"},
    "Stake": {
        "Career Page URL": "https://careers.getstake.com/",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/stake/jobs/",
    },
    "FlexxPay": {
        "Career Page URL": "https://www.flexxpay.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/flexxpay-fz-llc/jobs/",
    },
    "MoneyTap": {"Career Page URL": "https://www.moneytap.com/careers.html"},
    "PayU India": {
        "Career Page URL": "https://corporate.payu.in/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/payu/jobs/",
    },
    # --- Cred canonical opening board ----------------------------------------
    "Cred": {"Career Page URL": "https://careers.cred.club/openings"},
    # --- Reverify pass: empty / wrong-host fixes (India) -----------------------
    "Paytm": {"Career Page URL": "https://paytm.com/careers/"},
    "KreditBee": {"Career Page URL": "https://www.kreditbee.in/careers"},
    "LazyPay": {"Career Page URL": "https://www.lazypay.in/careers"},
    "Simpl": {"Career Page URL": "https://www.getsimpl.com/careers"},
    "BillDesk": {"Career Page URL": "https://www.billdesk.com/careers"},
    "MobiKwik": {"Career Page URL": "https://www.mobikwik.com/careers"},
    "Ezetap": {"Career Page URL": "https://www.ezetap.com/careers"},
    "Karza Technologies": {"Career Page URL": "https://www.karza.in/careers"},
    "NeoGrowth": {"Career Page URL": "https://www.neogrowth.in/careers"},
    "Wint Wealth": {"Career Page URL": "https://www.wintwealth.com/careers"},
    "Jiraaf": {"Career Page URL": "https://www.jiraaf.com/careers"},
    "IndiaLends": {"Career Page URL": "https://www.indialends.com/careers"},
    "Kaarva": {"Career Page URL": "https://www.kaarva.com/careers"},
    "Monexo": {"Career Page URL": "https://www.monexo.co/career"},
    "INDmoney": {"Career Page URL": "https://www.indmoney.com/careers"},
    "Tickertape": {"Career Page URL": "https://www.tickertape.in/careers"},
    "Bureau": {"Career Page URL": "https://jobs.bureau.id/"},
    "Capital Float": {"Career Page URL": "https://www.axio.co.in/careers"},
    "Vested Finance": {"Career Page URL": "https://vestedfinance.com/careers"},
    "Grip Invest": {"Career Page URL": "https://grip.recruitee.com/"},
    "OkCredit": {"Career Page URL": "https://okcredit.in/careers"},
    "myBillBook": {"Career Page URL": "https://mybillbook.in/careers"},
    "Axio": {"Career Page URL": "https://www.axio.co.in/careers"},
    "PowerUp Money": {"Career Page URL": "https://www.powerupmoney.ai/careers"},
    "TaxBuddy": {"Career Page URL": "https://www.taxbuddy.com/careers"},
    "Progcap": {"Career Page URL": "https://www.progcap.com/careers"},
    "CASHe": {"Career Page URL": "https://www.cashe.co.in/careers"},
    # Indian expense app (getwalnut → axio). Use brand domain so name/slug checks match "Walnut".
    "Walnut": {
        "Career Page URL": "https://www.getwalnut.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/walnutapp/jobs/",
    },
    # Wealth advisory (Mumbai). cube.global is a different company — official site is bankoncube.com.
    "Cube Wealth": {"Career Page URL": "https://www.bankoncube.com/careers"},
    "Tyke": {"Career Page URL": "https://tykeinvest.com/careers"},
    "MatchMove": {"Career Page URL": "https://www.matchmove.com/careers"},
    "Telr": {"Career Page URL": "https://www.telr.com/careers"},
    # --- US / EU fixes from reverify -----------------------------------------
    "Public.com": {"Career Page URL": "https://public.com/careers"},
    "Revolut": {"Career Page URL": "https://www.revolut.com/careers"},
    "Moov": {"Career Page URL": "https://moov.io/careers/"},
    # --- Singapore / SEA -------------------------------------------------------
    "Atome": {"Career Page URL": "https://hire-r1.mokahr.com/su/f4aa3"},
    # --- Middle East -----------------------------------------------------------
    "Chocolate Finance": {"Career Page URL": "https://www.chocolatefinance.com/"},
    "Baraka": {"Career Page URL": "https://getbaraka.com/careers"},
}


def main() -> None:
    df = pd.read_excel(XLSX, sheet_name=SHEET)
    applied = 0
    missing: list[str] = []
    for company, cols in PATCHES.items():
        m = df["Company Name"] == company
        if not m.any():
            missing.append(company)
            continue
        idx = df.index[m][0]
        for k, v in cols.items():
            df.at[idx, k] = v
        applied += 1
    df.to_excel(XLSX, sheet_name=SHEET, index=False)
    print(f"Patched {applied} companies -> {XLSX}")
    if missing:
        print("WARN: no row for:", ", ".join(missing))


if __name__ == "__main__":
    main()
