"""LinkedIn company posts Apify scraper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from job_scraper.models import Company
from job_scraper.scrapers.linkedin_posts import (
    LinkedInPostsScraper,
    apify_item_to_row,
    collect_standalone_target_page_urls,
    load_standalone_post_companies,
    normalize_linkedin_company_page_url,
)


def test_normalize_company_page_strips_jobs():
    assert (
        normalize_linkedin_company_page_url("https://www.linkedin.com/company/foo/jobs/")
        == "https://www.linkedin.com/company/foo/"
    )
    assert (
        normalize_linkedin_company_page_url("https://www.linkedin.com/company/foo/jobs")
        == "https://www.linkedin.com/company/foo/"
    )


def test_normalize_profile_url():
    assert (
        normalize_linkedin_company_page_url("https://www.linkedin.com/in/malay-krishna/")
        == "https://www.linkedin.com/in/malay-krishna/"
    )
    assert (
        normalize_linkedin_company_page_url(
            "https://www.linkedin.com/in/malay-krishna/recent-activity/all/"
        )
        == "https://www.linkedin.com/in/malay-krishna/"
    )


def test_normalize_company_page_strips_posts_and_query():
    assert (
        normalize_linkedin_company_page_url(
            "https://www.linkedin.com/company/vcjobsio/posts/?feedView=all"
        )
        == "https://www.linkedin.com/company/vcjobsio/"
    )
    assert (
        normalize_linkedin_company_page_url(
            "https://www.linkedin.com/company/pm-interview-prep-club/posts/"
        )
        == "https://www.linkedin.com/company/pm-interview-prep-club/"
    )


def test_collect_standalone_urls_from_env_string(monkeypatch):
    monkeypatch.delenv("LINKEDIN_POSTS_TARGET_URLS_FILE", raising=False)
    monkeypatch.delenv("LINKEDIN_POSTS_STANDALONE", raising=False)
    monkeypatch.setenv(
        "LINKEDIN_POSTS_TARGET_URLS",
        "https://www.linkedin.com/company/foo/posts/, https://www.linkedin.com/company/bar/jobs/",
    )
    urls = collect_standalone_target_page_urls()
    assert urls == [
        "https://www.linkedin.com/company/foo/",
        "https://www.linkedin.com/company/bar/",
    ]


def test_load_standalone_companies(monkeypatch):
    monkeypatch.delenv("LINKEDIN_POSTS_TARGET_URLS", raising=False)
    monkeypatch.delenv("LINKEDIN_POSTS_STANDALONE", raising=False)
    monkeypatch.setenv("LINKEDIN_POSTS_TARGET_URLS_FILE", "config/linkedin_posts_targets.txt")
    companies = load_standalone_post_companies()
    assert companies is not None
    assert len(companies) == 6
    assert any(c.name == "malay-krishna" for c in companies)
    assert companies[0].name == "pm-interview-prep-club"
    assert companies[0].linkedin_url == "https://www.linkedin.com/company/pm-interview-prep-club/"


def test_apify_item_to_row_prefers_text_and_url():
    row = apify_item_to_row(
        {
            "text": "Hello\nworld",
            "url": "https://www.linkedin.com/posts/foo",
            "postedAt": "2024-01-02",
        }
    )
    assert row["title"] == "Hello world"
    assert row["url"] == "https://www.linkedin.com/posts/foo"
    assert row["posted_at"] == "2024-01-02"
    assert row["__source__"] == "linkedin_posts:apify"


def test_linkedin_posts_scraper_calls_apify_with_target_urls():
    c = Company(
        name="Acme",
        careers_url="",
        linkedin_url="https://www.linkedin.com/company/acme/jobs/",
        country="",
        segment="",
    )
    sc = LinkedInPostsScraper(token="tok")
    fake = MagicMock()
    fake.json.return_value = [{"text": "Hi", "url": "https://linkedin.com/feed/update/1"}]
    fake.raise_for_status = MagicMock()
    with patch("job_scraper.scrapers.linkedin_posts.requests.post", return_value=fake) as post:
        rows = sc.fetch(c)
    post.assert_called_once()
    kwargs = post.call_args.kwargs
    assert kwargs["json"]["targetUrls"] == ["https://www.linkedin.com/company/acme/"]
    assert kwargs["json"]["maxPosts"] == 50
    assert kwargs["json"]["postedLimit"] == "month"
    assert len(rows) == 1
    assert rows[0]["title"] == "Hi"


def test_no_token_returns_empty():
    sc = LinkedInPostsScraper(token="")
    c = Company(name="X", linkedin_url="https://www.linkedin.com/company/x/jobs/")
    assert sc.fetch(c) == []
