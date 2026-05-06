"""Unit tests for `url_enrichment_core` verification helpers (mocked HTTP)."""

from __future__ import annotations

import pytest

import url_enrichment_core as uec


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected_subset",
    [
        ("Cred", {"cred"}),
        ("Pine Labs", {"pine", "pinelabs"}),
        ("Goldman Sachs Group, Inc.", {"goldman", "sachs"}),
        ("PolicyBazaar", {"policybazaar"}),
        ("HDFC Bank Ltd", {"hdfc", "bank"}),
    ],
)
def test_company_tokens(name, expected_subset):
    tokens = uec._company_tokens(name)
    assert expected_subset.issubset(tokens), f"{name} → {tokens}"


@pytest.mark.parametrize(
    "url,name,expected",
    [
        ("https://careers.cred.club/", "Cred", True),
        ("https://www.cred.club/careers", "Cred", True),
        ("https://grab.careers/en/jobs/", "Pine Labs", False),
        ("https://www.pinelabs.com/careers", "Pine Labs", True),
        ("https://tickets.paytm.com/trains/", "Paytm", True),
        ("https://www.freshersworld.com/jobs/.../bharatpe-1451827", "BharatPe", False),
        ("https://boards.greenhouse.io/cred/jobs/123", "Cred", True),
        ("https://boards.greenhouse.io/stripe/jobs/123", "Cred", False),
    ],
)
def test_domain_matches_company(url, name, expected):
    assert uec._domain_matches_company(url, name) is expected, f"{name} ↔ {url}"


@pytest.mark.parametrize(
    "url,is_aggr",
    [
        ("https://www.freshersworld.com/jobs/foo", True),
        ("https://www.careermine.com/jobs/", True),
        ("https://www.naukri.com/job-listings", True),
        ("https://jobs4fresher.com/upstox-off-campus-recruitment", True),
        ("https://glassdoor.com/jobs/cred", True),
        ("https://www.cred.club/careers", False),
        ("https://boards.greenhouse.io/cred/jobs/123", False),
    ],
)
def test_aggregator_blocklist(url, is_aggr):
    assert uec._is_aggregator(url) is is_aggr


def test_career_signals_keywords_present():
    html = "<html><body><h1>Open positions at Cred</h1><a>Apply Now</a></body></html>"
    assert uec._has_career_signals(html) is True


def test_career_signals_absent_on_unrelated_page():
    html = "<html><body><h1>Train tickets</h1><p>Book your journey.</p></body></html>"
    assert uec._has_career_signals(html) is False


# ---------------------------------------------------------------------------
# verify_career_url — combines all four checks
# ---------------------------------------------------------------------------


def _stub_http_get(monkeypatch, mapping):
    """Replace `_http_get` with a function that returns `mapping[url]` (or None)."""
    monkeypatch.setattr(uec, "_http_get", lambda url, timeout=8.0: mapping.get(url))


def test_verify_rejects_aggregator_without_fetching(monkeypatch):
    fetched: list[str] = []
    monkeypatch.setattr(uec, "_http_get", lambda url, timeout=8.0: fetched.append(url))
    assert uec.verify_career_url(
        "https://www.freshersworld.com/jobs/bharatpe", "BharatPe"
    ) is False
    assert fetched == []  # never fetched


def test_verify_rejects_wrong_domain_without_fetching(monkeypatch):
    fetched: list[str] = []
    monkeypatch.setattr(uec, "_http_get", lambda url, timeout=8.0: fetched.append(url))
    assert uec.verify_career_url("https://grab.careers/en/jobs/", "Pine Labs") is False
    assert fetched == []


def test_verify_rejects_404(monkeypatch):
    _stub_http_get(monkeypatch, {"https://www.cred.club/careers": (404, "<html></html>")})
    assert uec.verify_career_url("https://www.cred.club/careers", "Cred") is False


def test_verify_rejects_when_no_career_signals(monkeypatch):
    _stub_http_get(
        monkeypatch,
        {"https://tickets.paytm.com/trains/": (200, "<html><body>Train tickets</body></html>")},
    )
    assert uec.verify_career_url("https://tickets.paytm.com/trains/", "Paytm") is False


def test_verify_accepts_valid_career_page(monkeypatch):
    html = "<html><body><h1>Careers</h1><p>Open positions at Cred</p></body></html>"
    _stub_http_get(monkeypatch, {"https://careers.cred.club/": (200, html)})
    assert uec.verify_career_url("https://careers.cred.club/", "Cred") is True


def test_verify_skip_fetch_mode(monkeypatch):
    """fetch=False short-circuits at domain match — no HTTP made."""
    fetched: list[str] = []
    monkeypatch.setattr(uec, "_http_get", lambda url, timeout=8.0: fetched.append(url))
    assert uec.verify_career_url("https://careers.cred.club/", "Cred", fetch=False) is True
    assert fetched == []


# ---------------------------------------------------------------------------
# probe_official_career_paths — what powers the deterministic Cred lookup
# ---------------------------------------------------------------------------


def test_probe_returns_first_verified_path(monkeypatch):
    bad_html = "<html><body>404</body></html>"
    good_html = (
        "<html><body><h1>We're hiring at Cred</h1><a>Open positions</a></body></html>"
    )
    fetched: list[str] = []

    def fake_get(url, timeout=8.0):
        fetched.append(url)
        if url == "https://careers.cred.club/":
            return 200, good_html
        if url.endswith("/careers/") or url.endswith("/careers"):
            return 404, bad_html
        return None

    monkeypatch.setattr(uec, "_http_get", fake_get)

    out = uec.probe_official_career_paths("https://cred.club/", "Cred")
    assert out == "https://careers.cred.club/"
    assert "https://careers.cred.club/" in fetched


def test_probe_returns_empty_when_nothing_passes(monkeypatch):
    monkeypatch.setattr(uec, "_http_get", lambda url, timeout=8.0: None)
    assert uec.probe_official_career_paths("https://example.com/", "Acme") == ""
