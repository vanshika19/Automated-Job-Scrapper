"""LinkedIn profile or company posts via Apify (feed posts, not job listings).

Actor console: https://console.apify.com/actors/A3cAPGpwBEG8RJwse/input

**Targets**

- Workbook mode: each company's ``linkedin_url`` → one ``targetUrls`` entry (``/jobs`` and
  ``/posts`` stripped to the company root).
- Standalone list: set ``LINKEDIN_POSTS_STANDALONE=1`` to read ``config/linkedin_posts_targets.txt``,
  or ``LINKEDIN_POSTS_TARGET_URLS_FILE``, or ``LINKEDIN_POSTS_TARGET_URLS`` (comma / newline URLs).
  Use ``--source linkedin_posts`` **only** (CLI replaces the company list).

Optional ``LINKEDIN_POSTS_APIFY_INPUT_JSON`` is shallow-merged on top of defaults.
``targetUrls`` in that JSON is always overwritten per run from the URL above.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from ..models import Company

LOG = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_DEFAULT_POSTS_ACTOR = "A3cAPGpwBEG8RJwse"
APIFY_RUN_URL = (
    "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}"
)

_DEFAULT_INPUT: dict[str, Any] = {
    "includeQuotePosts": True,
    "includeReposts": True,
    "maxComments": 5,
    "maxPosts": 50,
    "maxReactions": 5,
    "postNestedComments": False,
    "postNestedReactions": False,
    "postedLimit": "1months",
    "scrapeComments": False,
    "scrapeReactions": False,
}


def normalize_linkedin_company_page_url(url: str) -> str:
    """Normalize company or profile URL for Apify ``targetUrls``."""
    u = (url or "").strip()
    if not u:
        return ""
    if "://" not in u:
        u = f"https://{u}"
    parsed = urlparse(u)
    if "linkedin.com" not in (parsed.netloc or "").lower():
        return ""
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower() or "www.linkedin.com"
    path = (parsed.path or "").rstrip("/")
    path = re.sub(r"/posts(?:/.*)?$", "", path, flags=re.I)
    path = re.sub(r"/jobs/?$", "", path)
    if "/company/" in path:
        return f"{scheme}://{netloc}{path}/"
    m = re.search(r"(/in/[^/?#]+)", path, re.I)
    if m:
        return f"{scheme}://{netloc}{m.group(1)}/"
    return ""


def _slug_from_company_url(normalized_url: str) -> str:
    for pattern in (r"/company/([^/?#]+)", r"/in/([^/?#]+)"):
        m = re.search(pattern, normalized_url, re.I)
        if m:
            return m.group(1).strip() or "linkedin"
    return "linkedin"


def _resolve_targets_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return _REPO_ROOT / p


def collect_standalone_target_page_urls() -> list[str]:
    """URLs for standalone post runs (deduped, normalized). Empty if not configured."""
    raw = os.environ.get("LINKEDIN_POSTS_TARGET_URLS", "").strip()
    if raw:
        parts = [p.strip() for p in re.split(r"[,;\n]+", raw) if p.strip()]
        out: list[str] = []
        seen: set[str] = set()
        for part in parts:
            n = normalize_linkedin_company_page_url(part)
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    env_file = os.environ.get("LINKEDIN_POSTS_TARGET_URLS_FILE", "").strip()
    path: Path | None = None
    if env_file:
        path = _resolve_targets_path(env_file)
    elif os.environ.get("LINKEDIN_POSTS_STANDALONE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        path = _REPO_ROOT / "config" / "linkedin_posts_targets.txt"
    if path is None:
        return []
    if not path.is_file():
        LOG.warning("LinkedIn posts standalone targets file not found: %s", path)
        return []
    out: list[str] = []
    seen: set[str] = set()
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        n = normalize_linkedin_company_page_url(line)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def load_standalone_post_companies() -> list[Company] | None:
    """Synthetic companies (slug name + company page URL) when a standalone URL list exists."""
    urls = collect_standalone_target_page_urls()
    if not urls:
        return None
    return [
        Company(
            name=_slug_from_company_url(u),
            careers_url="",
            linkedin_url=u,
            country="",
            segment="",
        )
        for u in urls
    ]


def _post_body(item: dict[str, Any]) -> str:
    for key in (
        "text",
        "content",
        "commentary",
        "postText",
        "description",
        "message",
    ):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    title = item.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return ""


def _post_url(item: dict[str, Any]) -> str:
    for key in ("url", "link", "postUrl", "permalink", "linkedinUrl"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _post_timestamp(item: dict[str, Any]) -> str:
    for key in ("postedAt", "posted_at", "createdAt", "date", "timestamp", "time"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if v is not None and not isinstance(v, str):
            return str(v)
    return ""


def apify_item_to_row(item: dict[str, Any]) -> dict[str, Any]:
    """Map arbitrary Apify post records into pipeline dicts."""
    body = _post_body(item)
    url = _post_url(item)
    one_line = body.replace("\n", " ").strip() if body else ""
    title = (one_line[:200] if one_line else "").strip() or "LinkedIn post"
    desc = (body[:4000] if body else json.dumps(item, default=str)[:4000])
    return {
        "title": title,
        "url": url,
        "location": "",
        "department": "linkedin_post",
        "description": desc,
        "posted_at": _post_timestamp(item),
        "__source__": "linkedin_posts:apify",
    }


class LinkedInPostsScraper:
    name = "linkedin_posts"

    def __init__(self, *, token: str | None = None) -> None:
        self.token = token or os.environ.get("APIFY_TOKEN", "").strip()

    def close(self) -> None:
        return

    def _payload_for_company(self, company: Company) -> dict[str, Any]:
        raw = os.environ.get("LINKEDIN_POSTS_APIFY_INPUT_JSON", "").strip()
        extra: dict[str, Any] = {}
        if raw:
            try:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    extra = loaded
                else:
                    LOG.warning("LINKEDIN_POSTS_APIFY_INPUT_JSON must be a JSON object; ignoring")
            except json.JSONDecodeError:
                LOG.warning("LINKEDIN_POSTS_APIFY_INPUT_JSON is not valid JSON; using defaults only")

        payload = {**_DEFAULT_INPUT, **extra}
        page = normalize_linkedin_company_page_url(company.linkedin_url or "")
        payload["targetUrls"] = [page]
        return payload

    def fetch(self, company: Company) -> list[dict]:
        if not self.token:
            LOG.debug("LinkedIn posts: no APIFY_TOKEN for %s", company.name)
            return []

        page = normalize_linkedin_company_page_url(company.linkedin_url or "")
        if not page:
            LOG.debug("LinkedIn posts: no company LinkedIn URL for %s", company.name)
            return []

        actor = os.environ.get("APIFY_LINKEDIN_POSTS_ACTOR", _DEFAULT_POSTS_ACTOR).strip()
        timeout_s = int(os.environ.get("LINKEDIN_POSTS_APIFY_TIMEOUT_SEC", "900"))
        api_url = APIFY_RUN_URL.format(actor=actor, token=self.token)
        payload = self._payload_for_company(company)

        try:
            r = requests.post(api_url, json=payload, timeout=timeout_s)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            LOG.warning("LinkedIn posts Apify failed for %s: %s", company.name, e)
            return []

        out: list[dict] = []
        for item in data or []:
            if not isinstance(item, dict):
                continue
            row = apify_item_to_row(item)
            if row.get("url") or row.get("description"):
                out.append(row)
        if not out:
            LOG.info("LinkedIn posts: 0 items returned for %s", company.name)
        return out
