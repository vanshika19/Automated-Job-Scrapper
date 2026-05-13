"""Generic career-page scraper (BeautifulSoup) with Playwright fallback.

Primary pass is static HTML via shared `job_harvest` heuristics. When the hub page
links to a same-site listing index (e.g. ``/careers/`` → ``/careers/jobs/``), we
fetch those listing URLs and merge anchors (see ``same_site_job_listing_urls``).

When that still returns no jobs, we optionally re-fetch the starting URL with
Playwright so JS-rendered listings can be harvested (same heuristics on rendered DOM).
"""

from __future__ import annotations

import logging
import os
from dataclasses import replace

from ..models import Company
from .base import http_get
from .job_harvest import (
    dedupe_jobs_by_url,
    drop_redundant_listing_hubs,
    harvest_job_links,
    same_site_job_listing_urls,
)

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
        norm_hub = url.split("#")[0].rstrip("/")
        listing_urls = same_site_job_listing_urls(r.text, url)
        for listing_url in listing_urls:
            if listing_url.split("#")[0].rstrip("/") == norm_hub:
                continue
            r2 = http_get(listing_url)
            if r2 is None or not r2.text:
                continue
            jobs.extend(
                harvest_job_links(
                    r2.text,
                    listing_url,
                    max_title_len=_STATIC_TITLE_MAX,
                    source="career",
                )
            )
        jobs = drop_redundant_listing_hubs(dedupe_jobs_by_url(jobs))

        if jobs or not self._playwright_fallback:
            return jobs

        try:
            self._pw = self._pw or PlaywrightScraper()
            pw_targets: list[str] = []
            seen: set[str] = set()
            for u in [url, *listing_urls]:
                uu = u.split("#")[0].strip()
                if uu and uu not in seen:
                    seen.add(uu)
                    pw_targets.append(uu)
            pw_targets = pw_targets[:5]
            LOG.info(
                "career static returned 0 jobs; trying Playwright (%d URLs) for %s",
                len(pw_targets),
                company.name,
            )
            for target in pw_targets:
                sub = replace(company, careers_url=target)
                out = self._pw.fetch(sub)
                if out:
                    return out
            return []
        except Exception as e:  # noqa: BLE001
            LOG.warning("Playwright fallback failed for %s: %s", company.name, e)
            return []


from .playwright_page import PlaywrightScraper  # noqa: E402  # import late — circular
