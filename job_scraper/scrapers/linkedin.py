"""LinkedIn scraper stub.

LinkedIn does not allow direct scraping of their job pages, so the recommended
path is an Apify actor (e.g. `bebity/linkedin-jobs-scraper`). This module is a
stub: it activates only when APIFY_TOKEN is set in the environment, otherwise
it returns an empty list and logs a warning.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import requests

from ..models import Company

LOG = logging.getLogger(__name__)

APIFY_ACTOR = os.environ.get("APIFY_LINKEDIN_ACTOR", "bebity~linkedin-jobs-scraper")
APIFY_RUN_URL = (
    "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}"
)


def _li_slug(url: str) -> str | None:
    m = re.search(r"linkedin\.com/company/([^/?#]+)", url or "", re.I)
    return m.group(1) if m else None


class LinkedInScraper:
    name = "linkedin"

    def __init__(self, *, token: str | None = None, max_items: int = 50) -> None:
        self.token = token or os.environ.get("APIFY_TOKEN", "").strip()
        self.max_items = max_items

    def fetch(self, company: Company) -> list[dict]:
        slug = _li_slug(company.linkedin_url)
        if not slug:
            return []
        if not self.token:
            LOG.warning("LinkedIn scrape skipped (no APIFY_TOKEN) for %s", company.name)
            return []

        payload: dict[str, Any] = {
            "companyNames": [slug],
            "rows": self.max_items,
        }
        url = APIFY_RUN_URL.format(actor=APIFY_ACTOR, token=self.token)
        try:
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            LOG.warning("Apify request failed for %s: %s", company.name, e)
            return []

        out: list[dict] = []
        for j in data or []:
            out.append(
                {
                    "title": j.get("title") or j.get("position"),
                    "url": j.get("link") or j.get("jobUrl"),
                    "location": j.get("location"),
                    "department": j.get("department") or "",
                    "description": j.get("description") or "",
                    "posted_at": j.get("postedTime") or j.get("postedAt") or "",
                    "__source__": "linkedin",
                }
            )
        return out
