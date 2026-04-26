"""SmartRecruiters (`careers.smartrecruiters.com/<company>` and embeds)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Extractor


class SmartRecruitersExtractor(Extractor):
    name = "smartrecruiters"

    @classmethod
    def matches(cls, url: str, html: str = "") -> bool:
        u = url.lower()
        if "smartrecruiters.com" in u:
            return True
        return "opening-job" in (html or "").lower()[:8000]

    def prepare(self, page: Any) -> None:
        try:
            page.wait_for_selector('li.opening-job, a.link--block', timeout=self.wait_ms)
        except Exception:  # noqa: BLE001
            super().prepare(page)

    def extract(self, html: str, base_url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        out: list[dict] = []
        seen: set[str] = set()

        for li in soup.select('li.opening-job, li[class*="job"], div[class*="opening-job"]'):
            a = li.select_one("a[href]")
            if not a:
                continue
            href = (a.get("href") or "").strip()
            absolute = urljoin(base_url, href)
            if not absolute or absolute in seen:
                continue
            title_el = li.select_one("h4, h3, .opening-job__title") or a
            title = title_el.get_text(" ", strip=True)
            if not title:
                continue

            location = ""
            loc_el = li.select_one('[class*="location"], li[class*="location"]')
            if loc_el:
                location = loc_el.get_text(" ", strip=True)

            department = ""
            dep_el = li.select_one('[class*="department"], [class*="category"]')
            if dep_el:
                department = dep_el.get_text(" ", strip=True)

            seen.add(absolute)
            out.append(
                {
                    "title": title,
                    "url": absolute,
                    "location": location,
                    "department": department,
                    "description": "",
                    "posted_at": "",
                    "__source__": "playwright:smartrecruiters",
                }
            )
        return out
