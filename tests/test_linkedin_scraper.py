"""Unit tests for LinkedIn URL normalization and HTML parsing (no Playwright)."""

from __future__ import annotations

from job_scraper.models import Company
from job_scraper.scrapers.linkedin import (
    LinkedInScraper,
    merge_linkedin_job_results,
    normalize_linkedin_jobs_url,
    parse_linkedin_company_jobs_html,
)


def test_normalize_appends_jobs_to_company_url():
    assert (
        normalize_linkedin_jobs_url("https://www.linkedin.com/company/stripe")
        == "https://www.linkedin.com/company/stripe/jobs/"
    )


def test_normalize_preserves_existing_jobs_path():
    assert (
        normalize_linkedin_jobs_url("https://www.linkedin.com/company/stripe/jobs")
        == "https://www.linkedin.com/company/stripe/jobs/"
    )


def test_parse_extracts_job_view_links():
    html = """
    <html><body>
      <a href="/jobs/view/12345">Software Engineer</a>
      <a href="https://www.linkedin.com/jobs/view/999?trk=abc">PM</a>
    </body></html>
    """
    jobs = parse_linkedin_company_jobs_html(html)
    urls = sorted(j["url"] for j in jobs)
    titles = {j["url"]: j["title"] for j in jobs}
    assert urls == [
        "https://www.linkedin.com/jobs/view/12345",
        "https://www.linkedin.com/jobs/view/999",
    ]
    assert titles["https://www.linkedin.com/jobs/view/12345"] == "Software Engineer"
    assert all(j["__source__"] == "linkedin:playwright" for j in jobs)


def test_parse_dedupes_same_job_id():
    html = """
    <a href="/jobs/view/1">A</a>
    <a href="/jobs/view/1">B</a>
    """
    assert len(parse_linkedin_company_jobs_html(html)) == 1


def test_linkedin_scraper_empty_without_url():
    c = Company(name="Acme", careers_url="", linkedin_url="")
    assert LinkedInScraper().fetch(c) == []


def test_merge_keeps_primary_when_same_job_id():
    apify = [
        {
            "title": "From Apify",
            "url": "https://www.linkedin.com/jobs/view/1",
            "__source__": "linkedin",
        }
    ]
    pw = [
        {
            "title": "From HTML",
            "url": "https://linkedin.com/jobs/view/1",
            "__source__": "linkedin:playwright",
        }
    ]
    merged = merge_linkedin_job_results(apify, pw)
    assert len(merged) == 1
    assert merged[0]["title"] == "From Apify"


def test_merge_appends_secondary_unique_job_ids():
    apify = [{"title": "One", "url": "https://www.linkedin.com/jobs/view/10"}]
    pw = [{"title": "Two", "url": "https://www.linkedin.com/jobs/view/20"}]
    merged = merge_linkedin_job_results(apify, pw)
    assert sorted(j["title"] for j in merged) == ["One", "Two"]
