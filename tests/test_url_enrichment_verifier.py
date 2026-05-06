"""Unit tests for the layered career-page verifier in `url_enrichment_core`.

Covers the pure (no-network) gates: aggregator blocklist, slug match, ATS host
slug check. Network paths are exercised via a monkey-patched `_http_get`.
"""

from __future__ import annotations

import pytest

from url_enrichment_core import (
    _domain_matches_company,
    _has_career_signals,
    _is_aggregator,
    _is_ats_host,
    verify_career_url,
)


# ---------------------------------------------------------------------------
# Aggregator blocklist
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.freshersworld.com/jobs/abc", True),
        ("https://www.indeed.com/jobs?q=engineer", True),
        ("https://www.glassdoor.co.in/Jobs/acme-jobs", True),
        ("https://www.naukri.com/cred-jobs", True),
        ("https://www.ambitionbox.com/jobs/x", True),
        ("https://cutshort.io/company/onecard", True),
        ("https://www.instahyre.com/jobs-at-ezetap", True),
        ("https://internshala.com/jobs/job-at-turtlemint/", True),
        ("https://www.shine.com/job-search/jobs-in-Navi", True),
        ("https://en.wikipedia.org/wiki/Acme", True),
        ("https://careers.cred.club/openings", False),
        ("https://www.cashfree.com/careers/", False),
        ("https://boards.greenhouse.io/acme", False),
    ],
)
def test_is_aggregator(url, expected):
    assert _is_aggregator(url) is expected


# ---------------------------------------------------------------------------
# ATS-host detection
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://boards.greenhouse.io/cred/jobs/123", True),
        ("https://job-boards.greenhouse.io/phonepe", True),
        ("https://jobs.lever.co/acme/abc", True),
        ("https://jobs.ashbyhq.com/cred", True),
        ("https://etmoney.zohorecruit.in/jobs/Careers", False),
        ("https://acme.myworkdayjobs.com/External", True),
        ("https://www.cashfree.com/careers/", False),
    ],
)
def test_is_ats_host(url, expected):
    assert _is_ats_host(url) is expected


# ---------------------------------------------------------------------------
# Domain match
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url,name,expected",
    [
        ("https://careers.cred.club/openings", "Cred", True),
        ("https://www.cashfree.com/careers/", "Cashfree", True),
        ("https://jupiter.money/careers", "Jupiter", True),
        ("https://www.pinelabs.com/careers", "Pine Labs", True),
        ("https://corporate.payu.in/careers", "PayU India", True),
        ("https://etmoney.zohorecruit.in/jobs/Careers", "ET Money", True),
        ("https://www.grab.careers/en/jobs/", "Pine Labs", False),
        ("https://careers.unilever.com/", "Fi Money", False),
        ("https://uchilife.actlever.co.jp/pulsepremiere/", "RazorpayX", False),
        ("https://www.zhihu.com/question/615604129", "Uni Cards", False),
        ("https://boards.greenhouse.io/razorpaysoftwareprivatelimited", "Razorpay", True),
        ("https://boards.greenhouse.io/grab", "Pine Labs", False),
        ("https://job-boards.greenhouse.io/phonepe", "PhonePe", True),
    ],
)
def test_domain_matches_company(url, name, expected):
    assert _domain_matches_company(url, name) is expected


# ---------------------------------------------------------------------------
# Career-signal sniff
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "html,expected",
    [
        ("<html><body><h1>Open Positions</h1></body></html>", True),
        ("<html><body><a>Apply now</a></body></html>", True),
        ("<html><body><h1>Welcome to our about page</h1></body></html>", False),
        ("", False),
        ("<html><body>We're hiring engineers!</body></html>", True),
    ],
)
def test_has_career_signals(html, expected):
    assert _has_career_signals(html) is expected


# ---------------------------------------------------------------------------
# verify_career_url — fast (URL-only) mode
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url,name,expected",
    [
        ("https://careers.cred.club/openings", "Cred", True),
        ("https://www.freshersworld.com/jobs/.../acko-1434913", "Acko", False),
        ("https://www.grab.careers/en/jobs/", "Pine Labs", False),
        ("https://boards.greenhouse.io/razorpaysoftwareprivatelimited", "Razorpay", True),
        ("https://boards.greenhouse.io/grab", "Pine Labs", False),
        ("https://etmoney.zohorecruit.in/jobs/Careers", "ET Money", True),
        ("https://uchilife.actlever.co.jp/pulsepremiere/", "RazorpayX", False),
    ],
)
def test_verify_career_url_no_fetch(url, name, expected):
    assert verify_career_url(url, name, fetch=False) is expected


# ---------------------------------------------------------------------------
# verify_career_url — full pipeline with mocked HTTP
# ---------------------------------------------------------------------------
def test_verify_career_url_accepts_when_fetch_returns_career_signals(monkeypatch):
    """Domain matches, fetch 200, page has 'open positions' → accept."""
    import url_enrichment_core as u

    def fake_get(url, timeout=8.0):
        return 200, "<html><body><h1>Open Positions</h1><p>Join Cred.</p></body></html>"

    monkeypatch.setattr(u, "_http_get", fake_get)
    assert u.verify_career_url("https://careers.cred.club/openings", "Cred")


def test_verify_career_url_rejects_dead_link(monkeypatch):
    """Domain matches, but server returned 404 → reject."""
    import url_enrichment_core as u

    monkeypatch.setattr(u, "_http_get", lambda url, timeout=8.0: (404, ""))
    assert not u.verify_career_url("https://careers.cred.club/openings", "Cred")


def test_verify_career_url_rejects_when_no_career_signals(monkeypatch):
    """Domain matches, page returns 200, but body has no career keywords → reject.

    This is the gate that catches `paytm.com/trains/`-style mis-pointed URLs.
    """
    import url_enrichment_core as u

    monkeypatch.setattr(
        u,
        "_http_get",
        lambda url, timeout=8.0: (200, "<html><body><p>Train tickets and bookings</p></body></html>"),
    )
    assert not u.verify_career_url("https://tickets.paytm.com/trains/", "Paytm")


def test_verify_career_url_rejects_when_request_fails(monkeypatch):
    """Network error → reject (we don't accept unverifiable URLs)."""
    import url_enrichment_core as u

    monkeypatch.setattr(u, "_http_get", lambda url, timeout=8.0: None)
    assert not u.verify_career_url("https://careers.cred.club/openings", "Cred")
