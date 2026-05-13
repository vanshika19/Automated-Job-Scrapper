"""ATS scrapers using public Greenhouse and Lever JSON APIs.

When ``Career Page URL`` is a marketing site (e.g. groww.in/careers) instead of the board
URL, we fetch that page once and look for Greenhouse / Lever links or embeds so boards
like ``job-boards.eu.greenhouse.io/groww`` are resolved without manual spreadsheet edits.
"""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from ..models import Company
from .base import http_get

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json"

_GH_HOSTS = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    # Regional boards (e.g. Groww — https://job-boards.eu.greenhouse.io/groww)
    "boards.eu.greenhouse.io",
    "job-boards.eu.greenhouse.io",
)
_LEVER_HOST = "jobs.lever.co"

# Full board URLs inside HTML (href, src, JSON snippets).
_GH_BOARD_URL_RE = re.compile(
    r"(?:https?://|//)(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/[^\s\"'<>]+",
    re.I,
)
_LEVER_BOARD_URL_RE = re.compile(
    r"(?:https?://|//)jobs\.lever\.co/[^\s\"'<>]+",
    re.I,
)
# Embedded job board iframe: .../embed/job_board?for=<slug>&...
_GH_EMBED_RE = re.compile(
    r"(?:https?://|//)(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/embed/job_board\?[^\s\"'<>]+",
    re.I,
)


def _trim_trailing_junk(url: str) -> str:
    u = url.strip().split("&quot;", 1)[0].strip()
    while u and u[-1] in ')\"\'>,.;':
        u = u[:-1]
    return u.rstrip("/")


def _normalize_job_board_url(raw: str) -> str:
    u = _trim_trailing_junk(raw.strip())
    if u.startswith("//"):
        return "https:" + u
    return u


def _looks_like_greenhouse_board_slug(slug: str) -> bool:
    if not slug or len(slug) < 2 or len(slug) > 80:
        return False
    if slug.isdigit():
        return False
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*$", slug))


def _greenhouse_slug_from_board_url(board_url: str) -> str | None:
    parsed = urlparse(board_url)
    parts = [s for s in parsed.path.split("/") if s]
    if not parts:
        return None
    # Listing pages use /embed/job_board?for=<slug> — not /{slug}/...
    if parts[0].lower() == "embed":
        return None
    slug = parts[0]
    return slug if _looks_like_greenhouse_board_slug(slug) else None


def _lever_slug_from_board_url(board_url: str) -> str | None:
    parsed = urlparse(board_url)
    host = (parsed.netloc or "").lower()
    if "jobs.lever.co" not in host:
        return None
    parts = [s for s in parsed.path.split("/") if s]
    if not parts:
        return None
    slug = parts[0]
    return slug if _looks_like_greenhouse_board_slug(slug) else None


def _greenhouse_slugs_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(slug: str | None) -> None:
        if slug and slug not in seen and _looks_like_greenhouse_board_slug(slug):
            seen.add(slug)
            ordered.append(slug)

    for m in _GH_BOARD_URL_RE.finditer(html):
        slug = _greenhouse_slug_from_board_url(_normalize_job_board_url(m.group(0)))
        add(slug)

    for m in _GH_EMBED_RE.finditer(html):
        embed_url = _normalize_job_board_url(m.group(0))
        qs = parse_qs(urlparse(embed_url).query)
        for vals in qs.get("for", []):
            add(vals)

    return ordered


def _lever_slugs_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(slug: str | None) -> None:
        if slug and slug not in seen and _looks_like_greenhouse_board_slug(slug):
            seen.add(slug)
            ordered.append(slug)

    for m in _LEVER_BOARD_URL_RE.finditer(html):
        slug = _lever_slug_from_board_url(_normalize_job_board_url(m.group(0)))
        add(slug)

    return ordered


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

        # Careers hub links out to GH/Lever (static HTML only — no JS execution).
        landing = http_get(url)
        if landing is None or not landing.text:
            return []
        html = landing.text

        for slug in _greenhouse_slugs_from_html(html):
            postings = _scrape_greenhouse(slug)
            if postings:
                for p in postings:
                    p["__source__"] = "ats:greenhouse"
                return postings

        for slug in _lever_slugs_from_html(html):
            postings = _scrape_lever(slug)
            if postings:
                for p in postings:
                    p["__source__"] = "ats:lever"
                return postings

        return []
