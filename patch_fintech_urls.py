#!/usr/bin/env python3
"""Apply hand-verified fixes for ambiguous company names."""

import pandas as pd

XLSX = "fintech_companies_structured.xlsx"
SHEET = "Fintech Companies"

PATCHES: dict[str, dict[str, str]] = {
    "Ramp": {
        "Career Page URL": "https://ramp.com/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/ramp/jobs/",
    },
    "Finverity": {
        "Career Page URL": "https://builtin.com/company/finverity/jobs",
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
    # Second pass: bad DDGS matches (aggregators, Wikipedia, wrong brands)
    "Stripe": {"Career Page URL": "https://stripe.com/jobs"},
    "Plaid": {"Career Page URL": "https://plaid.com/careers"},
    "Chime": {"Career Page URL": "https://careers.chime.com/en/jobs/"},
    "SoFi": {"Career Page URL": "https://www.sofi.com/careers"},
    "Lithic": {"Career Page URL": "https://job-boards.greenhouse.io/lithic"},
    "Apex Fintech": {
        "Career Page URL": "https://apexfintechsolutions.com/about/culture-careers/open-positions/"
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
        "Career Page URL": "https://www.flexxpay.com/en",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/flexxpay-fz-llc/jobs/",
    },
    "MoneyTap": {"Career Page URL": "https://www.moneytap.com/careers.html"},
    "PayU India": {
        "Career Page URL": "https://corporate.payu.in/careers",
        "LinkedIn Jobs URL": "https://www.linkedin.com/company/payu/jobs/",
    },
}


def main() -> None:
    df = pd.read_excel(XLSX, sheet_name=SHEET)
    for company, cols in PATCHES.items():
        m = df["Company Name"] == company
        if not m.any():
            continue

        idx = df.index[m][0]
        
        for k, v in cols.items():
            df.at[idx, k] = v
    df.to_excel(XLSX, sheet_name=SHEET, index=False)
    print("Patched", len(PATCHES), "companies ->", XLSX)


if __name__ == "__main__":
    main()
