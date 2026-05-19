"""Unit tests for LinkedIn URL normalization and HTML parsing (no Playwright)."""

from __future__ import annotations

from unittest.mock import patch

from job_scraper.models import Company
from job_scraper.parser import normalize
from job_scraper.scrapers.linkedin import (
    LinkedInScraper,
    _apify_csv_segments,
    _build_apify_jobs_payload,
    _employer_from_apify_item,
    _uses_rapid_linkedin_jobs_actor,
    apify_item_to_job_dict,
    apify_jobs_entries_count,
    merge_linkedin_job_results,
    normalize_linkedin_jobs_url,
    parse_linkedin_company_jobs_html,
)


def test_apify_csv_segments_splits_commas_and_newlines():
    assert _apify_csv_segments(None) is None
    assert _apify_csv_segments("  ") is None
    assert _apify_csv_segments("product manager, associate product manager") == [
        "product manager",
        "associate product manager",
    ]
    assert _apify_csv_segments("Bangalore,\nIndia") == ["Bangalore", "India"]
    assert _apify_csv_segments("Chennai;Hyderabad") == ["Chennai", "Hyderabad"]


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
            "__source__": "linkedin:apify",
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


def test_employer_from_apify_string_and_nested():
    assert _employer_from_apify_item({"companyName": " Stripe "}) == "Stripe"
    assert _employer_from_apify_item({"hiringCompany": {"name": "Acme Inc"}}) == "Acme Inc"


def test_normalize_prefers_employer_for_posting_company():
    c = Company(name="WorkbookCo", careers_url="", linkedin_url="")
    job = normalize(
        {
            "title": "PM",
            "url": "https://www.linkedin.com/jobs/view/1",
            "__employer__": "Real Employer",
        },
        c,
        "linkedin:apify",
    )
    assert job.company == "Real Employer"


def test_apify_jobs_entries_count_minimum_100(monkeypatch):
    monkeypatch.delenv("LINKEDIN_APIFY_JOBS_ENTRIES", raising=False)
    assert apify_jobs_entries_count(fallback=25) == 100
    assert apify_jobs_entries_count() == 100
    monkeypatch.setenv("LINKEDIN_APIFY_JOBS_ENTRIES", "250")
    assert apify_jobs_entries_count() == 250


def test_rapid_actor_payload_schema():
    c = Company(name="Acme", careers_url="", linkedin_url="", country="", segment="")
    p = _build_apify_jobs_payload(
        "JkfTWxtpgfvcRQn3p",
        title="product manager",
        location="India",
        rows=25,
        company=c,
        generic=True,
    )
    assert _uses_rapid_linkedin_jobs_actor("JkfTWxtpgfvcRQn3p")
    assert p["job_title"] == "product manager"
    assert p["location"] == "India"
    assert p["jobs_entries"] == 100
    assert "company_names" not in p


def test_apify_item_to_job_dict_rapid_columns():
    row = apify_item_to_job_dict(
        {
            "Job Title": "PM",
            "Job Url": "https://www.linkedin.com/jobs/view/1",
            "Company Name": "Stripe",
            "Job Location": "Bengaluru",
        }
    )
    assert row["title"] == "PM"
    assert row["url"] == "https://www.linkedin.com/jobs/view/1"
    assert row["__employer__"] == "Stripe"


def test_generic_apify_omits_company_name_and_calls_once(monkeypatch):
    monkeypatch.setenv("APIFY_LINKEDIN_ACTOR", "bebity~linkedin-jobs-scraper")
    monkeypatch.setenv("LINKEDIN_APIFY_GENERIC_SEARCH", "1")
    monkeypatch.setenv("LINKEDIN_APIFY_TITLE", "product manager")
    monkeypatch.setenv("LINKEDIN_APIFY_LOCATION", "India")
    monkeypatch.setenv("LINKEDIN_PLAYWRIGHT", "0")
    payloads: list[dict] = []

    def fake_post(url, json=None, timeout=None):
        payloads.append(json)
        fake_r = type("R", (), {})()
        fake_r.raise_for_status = lambda: None
        fake_r.json = lambda: [
            {
                "title": "PM",
                "url": "https://www.linkedin.com/jobs/view/99",
                "companyName": "Stripe",
            }
        ]
        return fake_r

    with patch("job_scraper.scrapers.linkedin.requests.post", side_effect=fake_post):
        s = LinkedInScraper(token="tok")
        a = Company(name="FintechA", careers_url="", linkedin_url="https://www.linkedin.com/company/a/jobs/")
        b = Company(name="FintechB", careers_url="", linkedin_url="https://www.linkedin.com/company/b/jobs/")
        ra = s.fetch(a)
        rb = s.fetch(b)

    assert len(payloads) == 1
    assert "companyName" not in payloads[0]
    assert payloads[0]["title"] == "product manager"
    assert payloads[0]["location"] == "India"
    assert len(ra) == 1
    assert ra[0]["__employer__"] == "Stripe"
    assert len(rb) == 0
