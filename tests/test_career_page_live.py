"""Live network test: hit a few fintech career pages and assert the scraper is sane.

Skipped by default. Opt in with:

    pytest -m live tests/test_career_page_live.py -s

Set LIVE_LIMIT to override how many companies to try (default 8).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

from job_scraper.registry import load_workbook
from job_scraper.scrapers.career_page import CareerPageScraper

LOG = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FINTECH_XLSX = REPO_ROOT / "fintech_companies_structured.xlsx"
ATS_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "myworkdayjobs.com", "smartrecruiters.com")


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not FINTECH_XLSX.exists(),
        reason=f"{FINTECH_XLSX.name} not present at repo root",
    ),
]


def _is_static_career_page(url: str) -> bool:
    """Cheap heuristic: skip URLs that are clearly handled by the ATS/Playwright scrapers."""
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return not any(h in host for h in ATS_HOSTS) and "linkedin.com" not in host


@pytest.fixture(scope="module")
def fintech_companies():
    return load_workbook(FINTECH_XLSX, "Fintech Companies", "Fintech")


def test_registry_loads(fintech_companies):
    """Sanity: the workbook loads and produces a non-trivial registry."""
    assert len(fintech_companies) > 10, "expected dozens of fintech rows"
    with_careers = [c for c in fintech_companies if c.careers_url]
    assert len(with_careers) > 5, "expected many fintech rows to have a careers_url"


def test_career_page_scraper_against_fintech_registry(fintech_companies):
    """Run the BeautifulSoup scraper against real fintech career pages and report yields.

    We don't enforce that every site returns jobs (some are JS-rendered and need
    Playwright). Instead we assert that:
      - at least one company in the sample produces a job dict
      - returned dicts have the expected shape
    """
    limit = int(os.environ.get("LIVE_LIMIT", "8"))
    sample = [c for c in fintech_companies if _is_static_career_page(c.careers_url)][:limit]

    if not sample:
        pytest.skip("no static-career-page candidates in the registry")

    scraper = CareerPageScraper()
    results: dict[str, list[dict]] = {}
    for company in sample:
        try:
            jobs = scraper.fetch(company)
        except Exception as e:  # noqa: BLE001
            LOG.warning("fetch crashed for %s (%s): %s", company.name, company.careers_url, e)
            jobs = []
        results[company.name] = jobs

    print("\n=== CareerPageScraper live yield ===")
    for name, jobs in results.items():
        company = next(c for c in sample if c.name == name)
        print(f"  {name:<32} {len(jobs):>4}  ({company.careers_url})")
        for j in jobs[:3]:
            print(f"      - {j['title'][:80]}  ->  {j['url']}")
    print(f"  -- {sum(len(v) for v in results.values())} jobs from {len(sample)} companies")

    total_jobs = sum(len(v) for v in results.values())
    assert total_jobs > 0, (
        "Expected at least one fintech static career page to yield a job. "
        "If this fails consistently, either the network is blocked or the "
        "registry's career_url fields mostly point to JS-rendered ATSes "
        "(in which case the Playwright source is the right tool)."
    )

    flat = [j for v in results.values() for j in v]
    expected = {"title", "url", "location", "department", "description", "posted_at", "__source__"}
    assert expected.issubset(flat[0].keys())
    assert all(j["__source__"] == "career" for j in flat)
    assert all(j["url"].startswith("http") for j in flat)
