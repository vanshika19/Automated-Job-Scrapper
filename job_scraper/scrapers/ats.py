"""ATS scrapers using public Greenhouse and Lever JSON APIs."""

from __future__ import annotations

import re
from typing import Iterable

from ..models import Company
from .base import http_get

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json"

_GH_HOSTS = ("boards.greenhouse.io", "job-boards.greenhouse.io")
_LEVER_HOST = "jobs.lever.co"


def _slug_from_url(url: str, host_parts: Iterable[str]) -> str | None:
    if not url:
        return None
    for h in host_parts:
        m = re.search(rf"https?://{re.escape(h)}/([^/?#]+)", url, re.I)
        if m:
            return m.group(1)
    return None


def _detect_greenhouse(url: str) -> str | None:
    return _slug_from_url(url, _GH_HOSTS)


def _detect_lever(url: str) -> str | None:
    return _slug_from_url(url, [_LEVER_HOST])


def _scrape_greenhouse(slug: str) -> list[dict]:
    r = http_get(GREENHOUSE_API.format(slug=slug))
    if r is None:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    out: list[dict] = []
    for j in data.get("jobs") or []:
        out.append(
            {
                "title": j.get("title"),
                "url": j.get("absolute_url"),
                "location": (j.get("location") or {}).get("name"),
                "department": ", ".join(d.get("name", "") for d in (j.get("departments") or [])),
                "description": j.get("content"),
                "posted_at": j.get("updated_at") or j.get("first_published"),
            }
        )
    return out


def _scrape_lever(slug: str) -> list[dict]:
    r = http_get(LEVER_API.format(slug=slug))
    if r is None:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    out: list[dict] = []
    for j in data:
        cats = j.get("categories") or {}
        out.append(
            {
                "title": j.get("text"),
                "url": j.get("hostedUrl") or j.get("applyUrl"),
                "location": cats.get("location"),
                "department": cats.get("department") or cats.get("team"),
                "description": j.get("descriptionPlain") or j.get("description"),
                "posted_at": j.get("createdAt"),
            }
        )
    return out


class ATSScraper:
    name = "ats"

    def fetch(self, company: Company) -> list[dict]:
        url = company.careers_url or ""
        gh = _detect_greenhouse(url)
        if gh:
            postings = _scrape_greenhouse(gh)
            for p in postings:
                p["__source__"] = "ats:greenhouse"
            return postings
        lv = _detect_lever(url)
        if lv:
            postings = _scrape_lever(lv)
            for p in postings:
                p["__source__"] = "ats:lever"
            return postings
        return []
