"""Shared pytest fixtures + project root on sys.path so `import job_scraper` works."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _fake_response(text: str, *, status: int = 200) -> SimpleNamespace:
    """Minimal stand-in for `requests.Response` — only the fields scrapers touch."""
    return SimpleNamespace(text=text, status_code=status, ok=status == 200)


@pytest.fixture
def fake_response():
    return _fake_response


@pytest.fixture
def stub_http_get(monkeypatch):
    """Replace `job_scraper.scrapers.career_page.http_get` with a recorded callable.

    Usage:
        def test_x(stub_http_get):
            calls = stub_http_get(lambda url: _fake_response("<html>...</html>"))
            ...                       # exercise scraper
            assert calls == ["http://..."]
    """
    from job_scraper.scrapers import career_page as cp

    def install(fn):
        calls: list[str] = []

        def wrapper(url, *_, **__):
            calls.append(url)
            return fn(url)

        monkeypatch.setattr(cp, "http_get", wrapper)
        return calls

    return install
