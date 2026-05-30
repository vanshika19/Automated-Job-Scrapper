"""ATS scrapers using public JSON APIs.

Supported platforms (direct URL or auto-detected from landing page HTML):
  Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Workday

When the Career Page URL is a marketing site, we fetch it once and scan for
ATS links.  Slugs are matched against the company name before use so that
portfolio job boards (e.g. jobs.accel.com) don't pollute results with a
random portfolio company's openings.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from ..models import Company
from .base import http_get, http_post

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json"
ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}"
RECRUITEE_API = "https://{slug}.recruitee.com/api/offers"

_GH_HOSTS = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "boards.eu.greenhouse.io",
    "job-boards.eu.greenhouse.io",
)
_LEVER_HOST = "jobs.lever.co"

# Regexes for finding ATS links inside HTML
_GH_BOARD_URL_RE = re.compile(
    r"(?:https?://|//)(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/[^\s\"'<>]+",
    re.I,
)
_LEVER_BOARD_URL_RE = re.compile(
    r"(?:https?://|//)jobs\.lever\.co/[^\s\"'<>]+",
    re.I,
)
_GH_EMBED_RE = re.compile(
    r"(?:https?://|//)(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/embed/job_board\?[^\s\"'<>]+",
    re.I,
)
_ASHBY_BOARD_URL_RE = re.compile(
    r"(?:https?://|//)jobs\.ashbyhq\.com/([^\s\"'<>/?#]+)",
    re.I,
)
_SMARTRECRUITERS_URL_RE = re.compile(
    r"(?:https?://|//)careers\.smartrecruiters\.com/([^\s\"'<>/?#]+)",
    re.I,
)
_RECRUITEE_URL_RE = re.compile(
    r"(?:https?://|//)([a-z0-9\-]+)\.recruitee\.com",
    re.I,
)
_WORKDAY_URL_RE = re.compile(
    r"https?://([\w\-]+\.wd\d+\.myworkdayjobs\.com)/(?:en-[A-Z]+/)?([^\s\"'<>/?#]+)",
    re.I,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trim_trailing_junk(url: str) -> str:
    u = url.strip().split("&quot;", 1)[0].strip()
    while u and u[-1] in ')\"\'>,.;':
        u = u[:-1]
    return u.rstrip("/")


def _normalize_url(raw: str) -> str:
    u = _trim_trailing_junk(raw.strip())
    return ("https:" + u) if u.startswith("//") else u


def _looks_like_slug(slug: str) -> bool:
    if not slug or len(slug) < 2 or len(slug) > 80:
        return False
    if slug.isdigit():
        return False
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-_]*$", slug))


_SLUG_STOP = frozenset({
    "the", "and", "for", "inc", "ltd", "llc", "pvt", "co", "group",
    "capital", "ventures", "venture", "partners", "growth", "india",
    "global", "management", "fund", "asset", "investments", "investment",
    "financial", "finance", "holdings", "tech", "technologies", "careers",
    "jobs", "hire", "work",
})


def _slug_matches_company(slug: str, company_name: str) -> bool:
    """True if the slug plausibly belongs to this company.

    Checks token overlap and substring containment after stripping noise words.
    A slug from a portfolio board (e.g. "6sense" for company "Accel Growth")
    will return False; a slug like "payhawkio" for "Payhawk" will return True.
    """
    def tokens(s: str) -> set[str]:
        parts = re.split(r"[\s\-_./]+", s.lower())
        return {p for p in parts if len(p) >= 3 and p not in _SLUG_STOP}

    slug_tokens = tokens(slug)
    name_tokens = tokens(company_name)
    if not slug_tokens or not name_tokens:
        return True  # can't tell; allow
    if slug_tokens & name_tokens:
        return True
    slug_flat = slug.lower().replace("-", "").replace("_", "")
    name_flat = re.sub(r"[\s\-_./]", "", company_name.lower())
    return slug_flat in name_flat or name_flat in slug_flat or name_flat[:8] in slug_flat


def _ms_to_iso(ts: int | float | None) -> str | None:
    """Convert Lever's millisecond Unix timestamp to ISO 8601."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# Direct-URL detectors
# ---------------------------------------------------------------------------

def _detect_greenhouse(url: str) -> str | None:
    for h in _GH_HOSTS:
        m = re.search(rf"https?://{re.escape(h)}/([^/?#]+)", url, re.I)
        if m:
            return m.group(1)
    return None


def _detect_lever(url: str) -> str | None:
    m = re.search(r"https?://jobs\.lever\.co/([^/?#]+)", url, re.I)
    return m.group(1) if m else None


def _detect_ashby(url: str) -> str | None:
    if "ashbyhq.com" not in url.lower():
        return None
    m = re.search(r"https?://jobs\.ashbyhq\.com/([^/?#]+)", url, re.I)
    return m.group(1) if m else None


def _detect_smartrecruiters(url: str) -> str | None:
    if "smartrecruiters.com" not in url.lower():
        return None
    m = re.search(r"https?://careers\.smartrecruiters\.com/([^/?#]+)", url, re.I)
    return m.group(1) if m else None


def _detect_recruitee(url: str) -> str | None:
    if "recruitee.com" not in url.lower():
        return None
    m = re.search(r"https?://([a-z0-9\-]+)\.recruitee\.com", url, re.I)
    return m.group(1) if m else None


def _detect_workday(url: str) -> tuple[str, str] | None:
    """Return (host, board) or None."""
    if "myworkdayjobs.com" not in url.lower():
        return None
    m = _WORKDAY_URL_RE.search(url)
    if not m:
        return None
    host = m.group(1)
    board = m.group(2).split("/")[0]  # strip any /job/... suffix
    return (host, board) if board else None


# ---------------------------------------------------------------------------
# API scrapers
# ---------------------------------------------------------------------------

def _scrape_greenhouse(slug: str) -> list[dict]:
    r = http_get(GREENHOUSE_API.format(slug=slug))
    if r is None:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    out = []
    for j in data.get("jobs") or []:
        out.append({
            "title": j.get("title"),
            "url": j.get("absolute_url"),
            "location": (j.get("location") or {}).get("name"),
            "department": ", ".join(d.get("name", "") for d in (j.get("departments") or [])),
            "description": j.get("content"),
            "posted_at": j.get("updated_at") or j.get("first_published"),
            "__source__": "ats:greenhouse",
        })
    return out


def _scrape_lever(slug: str) -> list[dict]:
    r = http_get(LEVER_API.format(slug=slug))
    if r is None:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    out = []
    for j in data:
        cats = j.get("categories") or {}
        out.append({
            "title": j.get("text"),
            "url": j.get("hostedUrl") or j.get("applyUrl"),
            "location": cats.get("location"),
            "department": cats.get("department") or cats.get("team"),
            "description": j.get("descriptionPlain") or j.get("description"),
            "posted_at": _ms_to_iso(j.get("createdAt")),  # Fix #3: ms → ISO
            "__source__": "ats:lever",
        })
    return out


def _scrape_ashby(slug: str) -> list[dict]:
    r = http_get(ASHBY_API.format(slug=slug))
    if r is None:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    out = []
    for j in data.get("jobPostings") or []:
        if not j.get("isListed", True):
            continue
        locs = j.get("secondaryLocations") or []
        location = j.get("locationName") or (locs[0].get("locationName") if locs else "")
        out.append({
            "title": j.get("title"),
            "url": j.get("jobUrl"),
            "location": location,
            "department": j.get("departmentName") or j.get("teamName"),
            "description": j.get("descriptionPlain") or "",
            "posted_at": j.get("publishedDate"),
            "__source__": "ats:ashby",
        })
    return out


def _scrape_smartrecruiters(slug: str) -> list[dict]:
    out = []
    offset = 0
    while True:
        r = http_get(SMARTRECRUITERS_API.format(slug=slug, offset=offset))
        if r is None:
            break
        try:
            data = r.json()
        except ValueError:
            break
        content = data.get("content") or []
        for j in content:
            loc = j.get("location") or {}
            location = ", ".join(filter(None, [loc.get("city"), loc.get("country")]))
            dep = (j.get("department") or {})
            out.append({
                "title": j.get("name"),
                "url": j.get("ref"),
                "location": location,
                "department": dep.get("label") or "",
                "description": "",
                "posted_at": j.get("releasedDate"),
                "__source__": "ats:smartrecruiters",
            })
        total = data.get("totalFound", 0)
        offset += 100
        if offset >= total or not content:
            break
    return out


def _scrape_recruitee(slug: str) -> list[dict]:
    r = http_get(RECRUITEE_API.format(slug=slug))
    if r is None:
        return []
    try:
        data = r.json()
    except ValueError:
        return []
    out = []
    for j in data.get("offers") or []:
        out.append({
            "title": j.get("title"),
            "url": j.get("careers_url") or j.get("url"),
            "location": j.get("location") or j.get("city"),
            "department": j.get("department"),
            "description": "",
            "posted_at": j.get("published_at"),
            "__source__": "ats:recruitee",
        })
    return out


def _scrape_workday(host: str, board: str) -> list[dict]:
    # Path uses subdomain only (e.g. "blackstone.wd1"), not the full host
    subdomain = host.replace(".myworkdayjobs.com", "")
    api_url = f"https://{host}/wday/cxs/{subdomain}/{board}/jobs"
    out = []
    offset = 0
    limit = 50
    base = f"https://{host}"
    while True:
        payload = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""}
        r = http_post(api_url, json=payload)
        if r is None:
            break
        try:
            data = r.json()
        except ValueError:
            break
        postings = data.get("jobPostings") or []
        for j in postings:
            path = j.get("externalPath", "")
            out.append({
                "title": j.get("title"),
                "url": base + path if path else None,
                "location": j.get("locationsText"),
                "department": "",
                "description": "",
                "posted_at": j.get("postedOn"),
                "__source__": "ats:workday",
            })
        total = data.get("total", 0)
        offset += limit
        if offset >= total or not postings:
            break
    return out


# ---------------------------------------------------------------------------
# HTML slug extractors
# ---------------------------------------------------------------------------

def _greenhouse_slug_from_board_url(board_url: str) -> str | None:
    parsed = urlparse(board_url)
    parts = [s for s in parsed.path.split("/") if s]
    if not parts or parts[0].lower() == "embed":
        return None
    slug = parts[0]
    return slug if _looks_like_slug(slug) else None


def _lever_slug_from_board_url(board_url: str) -> str | None:
    parsed = urlparse(board_url)
    if "jobs.lever.co" not in (parsed.netloc or "").lower():
        return None
    parts = [s for s in parsed.path.split("/") if s]
    return parts[0] if parts and _looks_like_slug(parts[0]) else None


def _greenhouse_slugs_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(slug: str | None) -> None:
        if slug and slug not in seen and _looks_like_slug(slug):
            seen.add(slug)
            ordered.append(slug)

    for m in _GH_BOARD_URL_RE.finditer(html):
        add(_greenhouse_slug_from_board_url(_normalize_url(m.group(0))))
    for m in _GH_EMBED_RE.finditer(html):
        qs = parse_qs(urlparse(_normalize_url(m.group(0))).query)
        for v in qs.get("for", []):
            add(v)
    return ordered


def _lever_slugs_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for m in _LEVER_BOARD_URL_RE.finditer(html):
        slug = _lever_slug_from_board_url(_normalize_url(m.group(0)))
        if slug and slug not in seen and _looks_like_slug(slug):
            seen.add(slug)
            ordered.append(slug)
    return ordered


def _ashby_slugs_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for m in _ASHBY_BOARD_URL_RE.finditer(html):
        slug = m.group(1).split("/")[0]
        if slug and slug not in seen and _looks_like_slug(slug):
            seen.add(slug)
            ordered.append(slug)
    return ordered


def _smartrecruiters_slugs_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for m in _SMARTRECRUITERS_URL_RE.finditer(html):
        slug = m.group(1).split("/")[0]
        if slug and slug not in seen and _looks_like_slug(slug):
            seen.add(slug)
            ordered.append(slug)
    return ordered


def _recruitee_slugs_from_html(html: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for m in _RECRUITEE_URL_RE.finditer(html):
        slug = m.group(1)
        if slug and slug not in seen and _looks_like_slug(slug):
            seen.add(slug)
            ordered.append(slug)
    return ordered


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class ATSScraper:
    name = "ats"

    def fetch(self, company: Company) -> list[dict]:
        url = company.careers_url or ""
        name = company.name or ""

        if not url:
            return []

        # 1. Direct ATS URL — no HTML fetch needed
        gh = _detect_greenhouse(url)
        if gh:
            return _scrape_greenhouse(gh)

        lv = _detect_lever(url)
        if lv:
            return _scrape_lever(lv)

        ashby = _detect_ashby(url)
        if ashby:
            return _scrape_ashby(ashby)

        sr = _detect_smartrecruiters(url)
        if sr:
            return _scrape_smartrecruiters(sr)

        rc = _detect_recruitee(url)
        if rc:
            return _scrape_recruitee(rc)

        wd = _detect_workday(url)
        if wd:
            return _scrape_workday(*wd)

        # 2. Landing page scan — fetch HTML and look for ATS links
        landing = http_get(url)
        if landing is None or not landing.text:
            return []
        html = landing.text

        _PLATFORMS: list[tuple] = [
            (_greenhouse_slugs_from_html, _scrape_greenhouse),
            (_lever_slugs_from_html,      _scrape_lever),
            (_ashby_slugs_from_html,      _scrape_ashby),
            (_smartrecruiters_slugs_from_html, _scrape_smartrecruiters),
            (_recruitee_slugs_from_html,  _scrape_recruitee),
        ]

        for slugs_fn, scrape_fn in _PLATFORMS:
            slugs = slugs_fn(html)
            if not slugs:
                continue

            # Fix #2: prefer slugs that match the company name.
            # If multiple slugs exist and none match, this is likely a portfolio
            # board — skip rather than returning a random portfolio company's jobs.
            matching = [s for s in slugs if _slug_matches_company(s, name)]
            if matching:
                for slug in matching:
                    postings = scrape_fn(slug)
                    if postings:
                        return postings
            elif len(slugs) == 1:
                # Single slug on page — safe to try even without a name match
                postings = scrape_fn(slugs[0])
                if postings:
                    return postings
            # else: multiple non-matching slugs → portfolio board, skip

        return []
