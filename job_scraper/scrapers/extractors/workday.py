"""Workday (`*.myworkdayjobs.com`)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Extractor


class WorkdayExtractor(Extractor):
    name = "workday"
    wait_ms = 6000

    @classmethod
    def matches(cls, url: str, html: str = "") -> bool:
        return "myworkdayjobs.com" in url.lower() or "workday" in (html or "").lower()[:4000]

    def prepare(self, page: Any) -> None:
        try:
            page.wait_for_selector('[data-automation-id="jobTitle"]', timeout=self.wait_ms)
        except Exception:  # noqa: BLE001
            super().prepare(page)

        for _ in range(8):
            try:
                more = page.query_selector('button[data-automation-id="loadMoreJobs"]')
                if not more or not more.is_visible():
                    break
                more.click()
                page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                break

    def extract(self, html: str, base_url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        out: list[dict] = []
        seen: set[str] = set()

        for li in soup.select('li.css-1q2dra3, li[class*="job"], section[data-automation-id="jobResults"] li'):
            title_a = li.select_one('a[data-automation-id="jobTitle"]') or li.select_one("a[href*='/job/']")
            if not title_a:
                continue
            href = (title_a.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(base_url, href)
            if absolute in seen:
                continue
            seen.add(absolute)

            location = ""
            loc_el = li.select_one('[data-automation-id="locations"], [class*="location"]')
            if loc_el:
                location = loc_el.get_text(" · ", strip=True)

            posted_at = ""
            posted_el = li.select_one('[data-automation-id="postedOn"]')
            if posted_el:
                posted_at = posted_el.get_text(" ", strip=True)

            out.append(
                {
                    "title": title_a.get_text(" ", strip=True),
                    "url": absolute,
                    "location": location,
                    "department": "",
                    "description": "",
                    "posted_at": posted_at,
                    "__source__": "playwright:workday",
                }
            )
        return out
