"""Ashby (jobs.ashbyhq.com / *.ashbyhq.com / embedded boards)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import Extractor


class AshbyExtractor(Extractor):
    name = "ashby"

    @classmethod
    def matches(cls, url: str, html: str = "") -> bool:
        u = url.lower()
        if "ashbyhq.com" in u or "/ashby_embed" in u:
            return True
        return "ashby-job-posting" in (html or "").lower()

    def prepare(self, page: Any) -> None:
        try:
            page.wait_for_selector(
                'a.ashby-job-posting-brief-link, [class*="JobPosting"] a',
                timeout=self.wait_ms,
            )
        except Exception:  # noqa: BLE001
            super().prepare(page)

    def extract(self, html: str, base_url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        out: list[dict] = []
        seen: set[str] = set()

        anchors = soup.select('a.ashby-job-posting-brief-link, a[href*="/ashby/"], a[href*="ashbyhq.com/"]')
        for a in anchors:
            href = (a.get("href") or "").strip()
            if not href:
                continue
            absolute = urljoin(base_url, href)
            if absolute in seen:
                continue

            title_el = a.select_one('[class*="title"], h3, h4') or a
            title = title_el.get_text(" ", strip=True)
            if not title:
                continue

            location = ""
            loc_el = a.select_one('[class*="location"]')
            if loc_el:
                location = loc_el.get_text(" ", strip=True)

            department = ""
            section = a.find_parent(re.compile(r"section|div"))
            if section is not None:
                heading = section.find(["h2", "h3"])
                if heading:
                    department = heading.get_text(" ", strip=True)

            seen.add(absolute)
            out.append(
                {
                    "title": title,
                    "url": absolute,
                    "location": location,
                    "department": department,
                    "description": "",
                    "posted_at": "",
                    "__source__": "playwright:ashby",
                }
            )
        return out
