"""Shared career-page job link harvesting (static HTML or Playwright snapshot).

Used by `CareerPageScraper` and `GenericExtractor` so URL heuristics stay in sync.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# mailto, auth walls, fragments; keep in sync with historical career parser behavior
BAD_HREF_HINTS = re.compile(
    r"#|mailto:|tel:|javascript:|/signin|/login|/cookies|/cookie|/register\b",
    re.I,
)

# Path / query fragments that usually indicate a job posting or ATS payload.
_JOB_PATH_OR_QUERY = re.compile(
    r"(?:[?&](?:gh_jid|job[Ii]d|job_id|currentJobId|funnelId)=[^&\s#]+)"
    r"|/(?:careers?|jobs?|job-board|job_board|opening[s]?|positions?|"
    r"opportunit(?:y|ies)|vacancies|vacancy|roles?|requisitions?)(?:/|\?|$)"
    r"|/(?:job|jobs)/[^/?#]+"
    r"|/company/[^/]+/jobs(?:/|\?|$)",
    re.I,
)

_ATS_NETLOC_MARKERS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "icims.com",
    "bamboohr.com",
    "applytojob.com",
    "workable.com",
    "hire.trakstar.com",
    "teamtailor.com",
    "jobvite.com",
    "eightfold.ai",
)


def _path_segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def _ats_board_job_shape(parsed, page_host: str) -> bool:
    """True when URL is on a known ATS host and plausibly points at one job or board."""
    host = parsed.netloc.lower()
    path_segs = _path_segments(parsed.path)

    if host.endswith("lever.co") and len(path_segs) >= 2:
        return True
    if "ashbyhq.com" in host and len(path_segs) >= 2:
        return True
    if "greenhouse.io" in host and "/jobs/" in parsed.path:
        return True
    if "greenhouse.io" in host and len(path_segs) >= 2 and host != page_host.lower():
        return True
    if any(m in host for m in _ATS_NETLOC_MARKERS) and _JOB_PATH_OR_QUERY.search(
        f"{parsed.path}?{parsed.query}"
    ):
        return True
    return False


def looks_like_job_href(absolute: str, page_host: str) -> bool:
    """Whether `absolute` is probably a job detail / board link from this careers page."""
    if not absolute or BAD_HREF_HINTS.search(absolute):
        return False
    parsed = urlparse(absolute)
    job_host = parsed.netloc.lower()
    ph = page_host.lower()
    cross_ok = _ats_board_job_shape(parsed, page_host) or any(
        m in job_host for m in _ATS_NETLOC_MARKERS
    )
    if job_host and job_host != ph and not cross_ok:
        return False
    if _ats_board_job_shape(parsed, page_host):
        return True
    needle = f"{parsed.path}?{parsed.query}"
    return bool(_JOB_PATH_OR_QUERY.search(needle))


def harvest_job_links(
    html: str,
    base_url: str,
    *,
    max_title_len: int,
    source: str,
) -> list[dict]:
    """Collect `<a href>` targets that look like job postings."""
    soup = BeautifulSoup(html, "lxml")
    host = urlparse(base_url).netloc
    seen: set[str] = set()
    out: list[dict] = []
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href:
            continue
        absolute = urljoin(base_url, href)
        if absolute in seen:
            continue
        if not looks_like_job_href(absolute, host):
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) > max_title_len:
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
                "__source__": source,
            }
        )
    return out
