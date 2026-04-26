"""Generic career-page scraper (BeautifulSoup).

This is intentionally a best-effort link harvester for sites that don't expose
Greenhouse/Lever. It pulls anchors that look like job postings, with the title
from the link text. JavaScript-rendered pages will need Playwright (TODO).
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..models import Company
from .base import http_get

_JOB_HINTS = re.compile(
    r"/(careers?|jobs?|opening[s]?|positions?|opportunit(?:y|ies)|vacancies)/",
    re.I,
)
_BAD_HINTS = re.compile(r"#|mailto:|tel:|javascript:|/signin|/login|/cookies", re.I)


class CareerPageScraper:
    name = "career"

    def fetch(self, company: Company) -> list[dict]:
        url = company.careers_url or ""
        if not url or "linkedin.com" in url:
            return []
        r = http_get(url)
        if r is None or not r.text:
            return []

        host = urlparse(url).netloc
        soup = BeautifulSoup(r.text, "lxml")
        seen: set[str] = set()
        out: list[dict] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or _BAD_HINTS.search(href):
                continue
            absolute = urljoin(url, href)
            if absolute in seen:
                continue
            parsed = urlparse(absolute)
            if parsed.netloc and parsed.netloc != host and "greenhouse" not in parsed.netloc and "lever" not in parsed.netloc and "ashby" not in parsed.netloc:
                continue
            if not _JOB_HINTS.search(parsed.path):
                continue
            title = a.get_text(" ", strip=True)
            if not title or len(title) > 120:
                continue
            seen.add(absolute)
            out.append(
                {
                    "title": title,
                    "url": absolute,
                    "location": "",
                    "department": "",
                    "description": "",
                    "posted_at": "",
                    "__source__": "career",
                }
            )
        return out
