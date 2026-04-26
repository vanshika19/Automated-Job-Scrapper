"""Base scraper interface and HTTP helpers."""

from __future__ import annotations

import logging
import time
from typing import Protocol

import requests

from ..models import Company

LOG = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; job-scrapper/0.1; +https://github.com/local)",
    "Accept": "text/html,application/json,*/*;q=0.8",
}


class Scraper(Protocol):
    name: str

    def fetch(self, company: Company) -> list[dict]: ...


def http_get(
    url: str,
    *,
    headers: dict | None = None,
    timeout: float = 15.0,
    retries: int = 2,
    backoff: float = 0.6,
) -> requests.Response | None:
    h = {**DEFAULT_HEADERS, **(headers or {})}
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=h, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                return r
            if r.status_code in (404, 410):
                return None
            last_err = RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as e:
            last_err = e
        time.sleep(backoff * (attempt + 1))
    LOG.debug("GET failed for %s: %s", url, last_err)
    return None
