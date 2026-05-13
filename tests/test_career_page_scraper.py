"""Unit tests for `CareerPageScraper` (no network calls)."""

from __future__ import annotations

import pytest

from job_scraper.models import Company
from job_scraper.scrapers.career_page import CareerPageScraper


def _company(careers: str = "https://acme.example.com/careers") -> Company:
    return Company(name="Acme", careers_url=careers, segment="Fintech")


def test_skips_when_no_careers_url():
    """No URL → return early, never touch the network."""
    assert CareerPageScraper().fetch(_company(careers="")) == []


def test_skips_linkedin_urls():
    """LinkedIn URLs are deliberately delegated to the LinkedIn scraper."""
    company = _company(careers="https://www.linkedin.com/company/acme/jobs/")
    assert CareerPageScraper().fetch(company) == []


def test_returns_empty_when_http_get_fails(stub_http_get):
    """If http_get returns None (HTTP error / network down), result is []."""
    calls = stub_http_get(lambda url: None)
    out = CareerPageScraper().fetch(_company())
    assert out == []
    assert calls == ["https://acme.example.com/careers"]


def test_extracts_basic_job_anchors(stub_http_get, fake_response):
    """Anchors with /jobs/ or /careers/ in the path are picked up."""
    html = """
    <html><body>
      <nav><a href="/about">About</a><a href="/contact">Contact</a></nav>
      <main>
        <a href="/careers/senior-engineer">Senior Software Engineer</a>
        <a href="/jobs/123-product-manager">Product Manager</a>
        <a href="/positions/marketing-lead">Marketing Lead</a>
      </main>
    </body></html>
    """
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())
    titles = sorted(j["title"] for j in out)

    assert titles == ["Marketing Lead", "Product Manager", "Senior Software Engineer"]
    assert all(j["url"].startswith("https://acme.example.com/") for j in out)
    assert all(j["__source__"] == "career" for j in out)


def test_resolves_relative_urls(stub_http_get, fake_response):
    """Relative hrefs like `/jobs/...` should be resolved against the base URL."""
    html = '<a href="/jobs/42-engineer">Engineer</a>'
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())

    assert len(out) == 1
    assert out[0]["url"] == "https://acme.example.com/jobs/42-engineer"


def test_drops_aggregator_and_external_links(stub_http_get, fake_response):
    """External hosts (other than the known ATSes) are filtered out."""
    html = """
    <a href="https://www.indeed.com/jobs?q=engineer">Engineer (Indeed)</a>
    <a href="https://glassdoor.com/jobs/acme">Engineer (Glassdoor)</a>
    <a href="/careers/data-scientist">Data Scientist</a>
    """
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())
    titles = [j["title"] for j in out]

    assert titles == ["Data Scientist"]


def test_keeps_cross_domain_greenhouse_links(stub_http_get, fake_response):
    """Greenhouse URLs on a different host are kept — their path contains /jobs/."""
    href = "https://boards.greenhouse.io/acme/jobs/12345"
    stub_http_get(lambda url: fake_response(f'<a href="{href}">Open Role</a>'))

    out = CareerPageScraper().fetch(_company())

    assert [j["url"] for j in out] == [href]


@pytest.mark.parametrize(
    "ats_host,href",
    [
        ("lever", "https://jobs.lever.co/acme/abcdef-engineer"),
        ("ashby", "https://jobs.ashbyhq.com/acme/role-1"),
    ],
)
def test_lever_and_ashby_board_urls_are_kept(stub_http_get, fake_response, ats_host, href):
    """Lever/Ashby board URLs use /{company}/{role-id} paths; treat as job links."""
    html = f'<a href="{href}">Open Role</a>'
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())

    assert [j["url"] for j in out] == [href]


def test_lever_or_ashby_links_with_jobs_in_path_are_kept(stub_http_get, fake_response):
    """Lever/Ashby links *do* survive the filter when the path includes a job hint."""
    href = "https://jobs.lever.co/acme/jobs/abcdef-engineer"
    stub_http_get(lambda url: fake_response(f'<a href="{href}">Open Role</a>'))

    out = CareerPageScraper().fetch(_company())

    assert [j["url"] for j in out] == [href]


def test_drops_bad_protocol_anchors(stub_http_get, fake_response):
    """mailto:/tel:/javascript: and login/cookie pages are skipped."""
    html = """
    <a href="mailto:hr@acme.com">Email HR</a>
    <a href="tel:+1234567890">Call us</a>
    <a href="javascript:void(0)">Apply</a>
    <a href="/signin/jobs">Sign in</a>
    <a href="#jobs-section">Jobs section</a>
    <a href="/careers/real-role">Real Role</a>
    """
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())

    assert [j["title"] for j in out] == ["Real Role"]


def test_dedupes_repeated_links(stub_http_get, fake_response):
    """The same href should only appear once even if linked multiple times."""
    html = """
    <a href="/jobs/123">Engineer</a>
    <a href="/jobs/123">Engineer (apply now)</a>
    <a href="/jobs/123">Engineer</a>
    """
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())

    assert len(out) == 1
    assert out[0]["url"] == "https://acme.example.com/jobs/123"


def test_drops_excessively_long_titles(stub_http_get, fake_response):
    """Anchors whose visible text > 120 chars are likely paragraphs, not job titles."""
    long_title = "A" * 130
    html = f"""
    <a href="/jobs/short">Real Job</a>
    <a href="/jobs/long">{long_title}</a>
    """
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())

    assert [j["title"] for j in out] == ["Real Job"]


def test_follows_careers_jobs_listing_on_same_site(stub_http_get, fake_response):
    """Marketing /careers/ links to /careers/jobs/ — fetch listing page for role anchors."""
    hub_html = '<html><body><a href="/careers/jobs/">See open positions</a></body></html>'
    listing_html = """<html><body>
      <a href="/careers/jobs/482-product">Product Lead</a>
    </body></html>"""
    base = "https://www.acko.example/careers/"
    calls: list[str] = []

    def route(url: str):
        calls.append(url)
        if url.rstrip("/").endswith("/careers"):
            return fake_response(hub_html)
        if "/careers/jobs" in url:
            return fake_response(listing_html)
        return fake_response("")

    stub_http_get(route)
    company = Company(name="Acko", careers_url=base, segment="Fintech")
    out = CareerPageScraper(playwright_fallback=False).fetch(company)

    assert len(calls) == 2
    assert any(j["title"] == "Product Lead" for j in out)


def test_returned_dict_shape(stub_http_get, fake_response):
    """Every returned dict has the keys the parser/pipeline expects."""
    html = '<a href="/careers/role">Role</a>'
    stub_http_get(lambda url: fake_response(html))

    out = CareerPageScraper().fetch(_company())

    assert len(out) == 1
    expected_keys = {"title", "url", "location", "department", "description", "posted_at", "__source__"}
    assert expected_keys.issubset(out[0].keys())
