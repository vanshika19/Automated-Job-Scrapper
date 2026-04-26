"""Catch-all extractor: anchor harvesting on the rendered HTML."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .base import Extractor

_JOB_HINTS = re.compile(
    r"/(careers?|jobs?|opening[s]?|positions?|opportunit(?:y|ies)|vacancies)/", re.I
)
_BAD_HINTS = re.compile(r"#|mailto:|tel:|javascript:|/signin|/login|/cookies", re.I)
_ATS_HOSTS = ("greenhouse", "lever", "ashby", "workday", "smartrecruiters", "myworkdayjobs")


class GenericExtractor(Extractor):
    name = "generic"

    @classmethod
    def matches(cls, url: str, html: str = "") -> bool:
        return True  # always matches as fallback

    def extract(self, html: str, base_url: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        host = urlparse(base_url).netloc
        seen: set[str] = set()
        out: list[dict] = []
        for a in soup.find_all("a", href=True):
            href = (a["href"] or "").strip()
            if not href or _BAD_HINTS.search(href):
                continue
            absolute = urljoin(base_url, href)
            if absolute in seen:
                continue
            parsed = urlparse(absolute)
            ext_ok = any(h in parsed.netloc for h in _ATS_HOSTS)
            if parsed.netloc and parsed.netloc != host and not ext_ok:
                continue
            if not _JOB_HINTS.search(parsed.path):
                continue
            title = a.get_text(" ", strip=True)
            if not title or len(title) > 160:
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
                    "__source__": "playwright:generic",
                }
            )
        return out
