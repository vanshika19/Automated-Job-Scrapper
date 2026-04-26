"""Detect embedded Greenhouse boards on rendered career pages.

Many companies host the page on their own domain but iframe in
`boards.greenhouse.io/<slug>`. When we detect that, hand control to the JSON
ATS API instead of scraping HTML — the API gives richer data anyway.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..ats import _scrape_greenhouse  # internal but stable
from .base import Extractor

_GH_IFRAME_RE = re.compile(
    r"https?://(?:job-)?boards(?:-api)?\.greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_\-]+)",
    re.I,
)


class GreenhouseIframeExtractor(Extractor):
    name = "greenhouse_iframe"

    @classmethod
    def matches(cls, url: str, html: str = "") -> bool:
        if not html:
            return False
        return bool(_GH_IFRAME_RE.search(html))

    def extract(self, html: str, base_url: str) -> list[dict]:
        slug = self._slug(html)
        if not slug:
            return []
        postings = _scrape_greenhouse(slug)
        for p in postings:
            p["__source__"] = "playwright:greenhouse-iframe"
        return postings

    def _slug(self, html: str) -> str | None:
        m = _GH_IFRAME_RE.search(html)
        if not m:
            return None
        slug = m.group(1)
        if "?" in slug or "/" in slug:
            slug = slug.split("?")[0].split("/")[0]
        return slug

    @staticmethod
    def _iframe_src(html: str) -> str | None:
        soup = BeautifulSoup(html, "lxml")
        for f in soup.find_all("iframe", src=True):
            host = urlparse(f["src"]).netloc
            if "greenhouse.io" in host:
                return f["src"]
        return None
