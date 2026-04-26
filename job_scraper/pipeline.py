"""Pipeline orchestration: registry -> scrapers -> parse -> filter -> dedup -> store."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .dedup import dedupe
from .filters import FilterRules, apply as apply_filter
from .models import Company, JobPosting
from .parser import normalize_many
from .scrapers import ATSScraper, CareerPageScraper, LinkedInScraper, PlaywrightScraper
from .scrapers.base import Scraper
from .storage import Storage

LOG = logging.getLogger("job_scraper.pipeline")

SOURCE_REGISTRY: dict[str, type[Scraper]] = {
    "ats": ATSScraper,
    "career": CareerPageScraper,
    "playwright": PlaywrightScraper,
    "linkedin": LinkedInScraper,
}


@dataclass
class RunStats:
    companies: int = 0
    raw: int = 0
    kept: int = 0
    inserted: int = 0
    refreshed: int = 0
    closed: int = 0
    duration_s: float = 0.0


def _build_scrapers(sources: Sequence[str]) -> list[Scraper]:
    out: list[Scraper] = []
    for s in sources:
        cls = SOURCE_REGISTRY.get(s)
        if not cls:
            LOG.warning("Unknown source %r, skipping", s)
            continue
        out.append(cls())
    return out


def run(
    companies: Iterable[Company],
    db_url: str | Path,
    *,
    sources: Sequence[str] = ("ats", "career"),
    rules: FilterRules | None = None,
    sleep_per_company: float = 0.4,
    mark_stale_older_than: str | None = None,
) -> RunStats:
    start = time.monotonic()
    scrapers = _build_scrapers(sources)
    stats = RunStats()

    with Storage(db_url) as db:
        company_list = list(companies)
        db.upsert_companies(company_list)
        stats.companies = len(company_list)

        for idx, company in enumerate(company_list, 1):
            collected: list[JobPosting] = []
            for sc in scrapers:
                try:
                    raws = sc.fetch(company)
                except Exception as e:  # noqa: BLE001
                    LOG.warning("%s failed for %s: %s", sc.name, company.name, e)
                    continue
                stats.raw += len(raws)
                for r in raws:
                    src = r.get("__source__") or sc.name
                    for job in normalize_many([r], company, src):
                        collected.append(job)

            kept = list(apply_filter(dedupe(collected), rules))
            stats.kept += len(kept)
            ins, ref = db.upsert_jobs(kept)
            stats.inserted += ins
            stats.refreshed += ref
            LOG.info(
                "[%d/%d] %s -> raw=%d kept=%d new=%d refreshed=%d",
                idx,
                len(company_list),
                company.name,
                len(collected),
                len(kept),
                ins,
                ref,
            )
            if sleep_per_company:
                time.sleep(sleep_per_company)

        if mark_stale_older_than:
            stats.closed = db.mark_stale(mark_stale_older_than)

    for sc in scrapers:
        close_fn = getattr(sc, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:  # noqa: BLE001
                pass

    stats.duration_s = round(time.monotonic() - start, 2)
    return stats
