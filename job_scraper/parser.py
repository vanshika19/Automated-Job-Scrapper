"""Normalize raw scraper dicts into JobPosting instances."""

from __future__ import annotations

import re
from typing import Iterable, Iterator
from urllib.parse import urljoin, urlparse

from .models import Company, JobPosting

_WS = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return _WS.sub(" ", str(text)).strip()


def _abs_url(url: str | None, base: str | None = None) -> str:
    if not url:
        return ""
    u = url.strip()
    if not u:
        return ""
    if urlparse(u).scheme:
        return u
    if base:
        return urljoin(base, u)
    return u


def normalize(raw: dict, company: Company, source: str) -> JobPosting:
    return JobPosting(
        company=company.name,
        title=_clean(raw.get("title") or raw.get("name")),
        url=_abs_url(raw.get("url") or raw.get("absolute_url") or raw.get("hostedUrl"), company.careers_url),
        location=_clean(
            raw.get("location")
            or (raw.get("categories") or {}).get("location")
            or ""
        ),
        department=_clean(
            raw.get("department")
            or (raw.get("categories") or {}).get("team")
            or ""
        ),
        description=_clean(raw.get("description") or raw.get("descriptionPlain") or "")[:4000],
        source=source,
        posted_at=_clean(raw.get("posted_at") or raw.get("createdAt") or raw.get("updated_at")),
    )


def normalize_many(
    raws: Iterable[dict], company: Company, source: str
) -> Iterator[JobPosting]:
    for r in raws:
        if not r:
            continue
        job = normalize(r, company, source)
        if job.title:
            yield job
