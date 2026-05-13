"""ATS scraper: Greenhouse/Lever API + board discovery from careers landing HTML."""

from __future__ import annotations

from job_scraper.models import Company
from job_scraper.scrapers.ats import ATSScraper, _greenhouse_slugs_from_html


class _FakeResp:
    def __init__(self, *, text: str = "", json_data: dict | None = None) -> None:
        self.text = text
        self.ok = True
        self._json_data = json_data

    def json(self) -> dict:
        return self._json_data if self._json_data is not None else {}


def test_greenhouse_slugs_from_html_href_eu_board():
    html = '<a href="https://job-boards.eu.greenhouse.io/groww">View openings</a>'
    assert _greenhouse_slugs_from_html(html) == ["groww"]


def test_greenhouse_slugs_from_embed_for_param():
    html = (
        'src="//boards.greenhouse.io/embed/job_board?for=acme&token=x" '
        'other="https://job-boards.eu.greenhouse.io/embed/job_board?for=groww"'
    )
    slugs = _greenhouse_slugs_from_html(html)
    assert "acme" in slugs and "groww" in slugs


def test_fetch_resolves_board_from_marketing_landing(monkeypatch):
    landing_html = (
        '<html><body>'
        '<a href="https://job-boards.eu.greenhouse.io/groww">Careers</a>'
        "</body></html>"
    )
    api_payload = {
        "jobs": [
            {
                "title": "Platform Engineer",
                "absolute_url": "https://job-boards.eu.greenhouse.io/groww/jobs/1",
                "location": {"name": "Bengaluru"},
                "departments": [{"name": "Engineering"}],
                "content": "",
                "updated_at": "2025-01-01",
            }
        ]
    }

    def fake_http_get(url: str, **_):
        if "groww.in" in url:
            return _FakeResp(text=landing_html)
        if "boards-api.greenhouse.io" in url and "/boards/groww/" in url:
            return _FakeResp(json_data=api_payload)
        return _FakeResp(text="")

    monkeypatch.setattr("job_scraper.scrapers.ats.http_get", fake_http_get)

    company = Company(
        name="Groww",
        careers_url="https://groww.in/careers",
        linkedin_url="",
        country="",
        segment="Fintech",
    )
    out = ATSScraper().fetch(company)
    assert len(out) == 1
    assert out[0]["title"] == "Platform Engineer"
    assert out[0]["__source__"] == "ats:greenhouse"


def test_direct_greenhouse_url_skips_landing_scan(monkeypatch):
    calls: list[str] = []

    def fake_http_get(url: str, **_):
        calls.append(url)
        return _FakeResp(
            json_data={"jobs": [{"title": "X", "absolute_url": "https://x", "location": {"name": ""}, "departments": [], "content": "", "updated_at": ""}]}
        )

    monkeypatch.setattr("job_scraper.scrapers.ats.http_get", fake_http_get)

    company = Company(
        name="Acme",
        careers_url="https://job-boards.greenhouse.io/acme",
        linkedin_url="",
        country="",
        segment="",
    )
    ATSScraper().fetch(company)
    assert calls == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"]
