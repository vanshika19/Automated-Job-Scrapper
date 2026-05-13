"""Unit tests for job listing helpers (no HTTP)."""

from __future__ import annotations

from job_scraper.scrapers.job_harvest import (
    dedupe_jobs_by_url,
    drop_redundant_listing_hubs,
    path_is_job_listing_index,
    same_site_job_listing_urls,
)


def test_path_is_job_listing_index():
    assert path_is_job_listing_index("/careers/jobs/")
    assert path_is_job_listing_index("/careers/jobs")
    assert path_is_job_listing_index("/jobs/")
    assert path_is_job_listing_index("/foo/careers/jobs")
    assert not path_is_job_listing_index("/careers/jobs/482-product-manager")
    assert not path_is_job_listing_index("/about")


def test_same_site_job_listing_urls_finds_hub_links():
    html = '<a href="/careers/jobs/">See openings</a><a href="https://evil.com/jobs">x</a>'
    urls = same_site_job_listing_urls(html, "https://www.acko.com/careers/")
    assert urls
    assert urls[0].rstrip("/") == "https://www.acko.com/careers/jobs"


def test_drop_redundant_listing_hubs():
    jobs = [
        {"url": "https://x.com/careers/jobs", "title": "See openings"},
        {"url": "https://x.com/careers/jobs/pm", "title": "PM"},
    ]
    out = drop_redundant_listing_hubs(dedupe_jobs_by_url(jobs))
    assert len(out) == 1
    assert out[0]["title"] == "PM"
