"""Generic career-page scraper (BeautifulSoup) with Playwright fallback.

Primary pass is static HTML via shared `job_harvest` heuristics. When that returns
no jobs, we optionally re-fetch the same URL with Playwright so JS-rendered
listings can be harvested (same heuristics on rendered DOM).
"""

from __future__ import annotations

import logging
import os

from ..models import Company
from .base import http_get
from .job_harvest import harvest_job_links

LOG = logging.getLogger(__name__)

_STATIC_TITLE_MAX = 120


class CareerPageScraper:
    name = "career"

    def __init__(self, *, playwright_fallback: bool | None = None) -> None:
        if playwright_fallback is None:
            raw = os.environ.get("CAREER_PLAYWRIGHT_FALLBACK", "1").strip().lower()
            playwright_fallback = raw not in ("0", "false", "no", "off")
        self._playwright_fallback = playwright_fallback
        self._pw: PlaywrightScraper | None = None

    def close(self) -> None:
        if self._pw is not None:
            self._pw.close()
            self._pw = None

    def fetch(self, company: Company) -> list[dict]:
        url = company.careers_url or ""
        if not url or "linkedin.com" in url:
            return []
        r = http_get(url)
        if r is None or not r.text:
            return []

        jobs = harvest_job_links(r.text, url, max_title_len=_STATIC_TITLE_MAX, source="career")
        if jobs or not self._playwright_fallback:
            return jobs

        try:
            self._pw = self._pw or PlaywrightScraper()
            LOG.info("career static returned 0 jobs; trying Playwright for %s", company.name)
            return self._pw.fetch(company)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Playwright fallback failed for %s: %s", company.name, e)
            return []


from .playwright_page import PlaywrightScraper  # noqa: E402  # import late — circular
