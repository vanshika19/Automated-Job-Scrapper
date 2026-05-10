"""LinkedIn company jobs: Apify (when ``APIFY_TOKEN`` is set) plus best-effort page harvest.

The company's LinkedIn ``/company/{slug}/jobs/`` page is optionally rendered in headless
Chromium and ``/jobs/view/{id}`` links are parsed. That pass runs alongside Apify when
both are enabled so URL-derived listings can complement the actor dataset. The HTML parse
is brittle (login walls, layout changes); Apify remains the primary source when configured.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..models import Company

LOG = logging.getLogger(__name__)

APIFY_ACTOR = os.environ.get("APIFY_LINKEDIN_ACTOR", "bebity~linkedin-jobs-scraper")
APIFY_RUN_URL = (
    "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}"
)

_LI_VIEW = re.compile(r"linkedin\.com/jobs/view/(\d+)", re.I)


def _li_slug(url: str) -> str | None:
    m = re.search(r"linkedin\.com/company/([^/?#]+)", url or "", re.I)
    return m.group(1) if m else None


def normalize_linkedin_jobs_url(url: str) -> str:
    """Ensure URL targets the company jobs tab when possible."""
    u = (url or "").strip()
    if not u:
        return ""
    parsed = urlparse(u if "://" in u else f"https://{u}")
    if "linkedin.com" not in parsed.netloc.lower():
        return u
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower() or "www.linkedin.com"
    path = (parsed.path or "").rstrip("/")
    if "/company/" in path and "/jobs" not in path:
        path = f"{path}/jobs"
    elif not path or path == "":
        return u
    return f"{scheme}://{netloc}{path}/"


def parse_linkedin_company_jobs_html(html: str) -> list[dict]:
    """Extract job postings from a LinkedIn company jobs HTML snapshot."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    out: list[dict] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        abs_url = href if href.startswith("http") else urljoin("https://www.linkedin.com", href)
        m = _LI_VIEW.search(abs_url)
        if not m:
            continue
        jid = m.group(1)
        canonical = f"https://www.linkedin.com/jobs/view/{jid}"
        if canonical in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            title = (a.get("aria-label") or "").strip()
        if not title:
            title = f"Job {jid}"
        title = title[:200]
        seen.add(canonical)
        out.append(
            {
                "title": title,
                "url": canonical,
                "location": "",
                "department": "",
                "description": "",
                "posted_at": "",
                "__source__": "linkedin:playwright",
            }
        )
    return out


def merge_linkedin_job_results(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """Dedupe by LinkedIn ``jobs/view/{id}`` when present; otherwise by normalized URL."""
    seen: set[str] = set()
    out: list[dict] = []

    def key_for(job: dict) -> str | None:
        u = (job.get("url") or "").strip()
        if not u:
            return None
        m = _LI_VIEW.search(u)
        if m:
            return f"view:{m.group(1)}"
        return f"url:{u.lower()}"

    for job in primary:
        k = key_for(job)
        if k and k not in seen:
            seen.add(k)
            out.append(job)
    for job in secondary:
        k = key_for(job)
        if k and k not in seen:
            seen.add(k)
            out.append(job)
    return out


class LinkedInScraper:
    name = "linkedin"

    def __init__(self, *, token: str | None = None, max_items: int = 50) -> None:
        self.token = token or os.environ.get("APIFY_TOKEN", "").strip()
        self.max_items = max_items
        self._pw = None
        self._browser = None

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._browser = None
        self._pw = None

    def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "playwright not installed. Run `pip install playwright && playwright install chromium`."
            ) from e
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)

    def _fetch_apify(self, company: Company, slug: str) -> list[dict]:
        payload: dict[str, Any] = {
            "companyNames": [slug],
            "rows": self.max_items,
        }
        url = APIFY_RUN_URL.format(actor=APIFY_ACTOR, token=self.token)
        try:
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            LOG.warning("Apify request failed for %s: %s", company.name, e)
            return []

        out: list[dict] = []
        for j in data or []:
            out.append(
                {
                    "title": j.get("title") or j.get("position"),
                    "url": j.get("link") or j.get("jobUrl"),
                    "location": j.get("location"),
                    "department": j.get("department") or "",
                    "description": j.get("description") or "",
                    "posted_at": j.get("postedTime") or j.get("postedAt") or "",
                    "__source__": "linkedin",
                }
            )
        return out

    def _fetch_playwright(self, company: Company) -> list[dict]:
        if os.environ.get("LINKEDIN_PLAYWRIGHT", "1").strip().lower() in (
            "0",
            "false",
            "no",
            "off",
        ):
            LOG.info("LinkedIn Playwright disabled (LINKEDIN_PLAYWRIGHT=0) for %s", company.name)
            return []

        raw_url = company.linkedin_url or ""
        url = normalize_linkedin_jobs_url(raw_url)
        if not url:
            return []

        wait_ms = int(os.environ.get("LINKEDIN_PLAYWRIGHT_WAIT_MS", "5000"))

        try:
            self._ensure_browser()
        except Exception as e:  # noqa: BLE001
            LOG.warning("LinkedIn Playwright unavailable for %s: %s", company.name, e)
            return []

        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        page = ctx.new_page()
        try:
            page.goto(url, timeout=90_000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
            except Exception:  # noqa: BLE001
                pass
            html = page.content()
        except Exception as e:  # noqa: BLE001
            LOG.warning("LinkedIn page load failed for %s: %s", company.name, e)
            return []
        finally:
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass

        jobs = parse_linkedin_company_jobs_html(html)
        if not jobs:
            LOG.info(
                "LinkedIn Playwright returned 0 jobs for %s (login wall or layout change?)",
                company.name,
            )
        if len(jobs) > self.max_items:
            jobs = jobs[: self.max_items]
        return jobs

    def fetch(self, company: Company) -> list[dict]:
        slug = _li_slug(company.linkedin_url)
        if not slug:
            return []

        apify_jobs: list[dict] = []
        if self.token:
            apify_jobs = self._fetch_apify(company, slug)
        else:
            LOG.debug("LinkedIn: no APIFY_TOKEN for %s", company.name)

        pw_jobs = self._fetch_playwright(company)
        if self.token and pw_jobs:
            LOG.debug(
                "LinkedIn: merging Apify (%d) + page harvest (%d) for %s",
                len(apify_jobs),
                len(pw_jobs),
                company.name,
            )

        merged = merge_linkedin_job_results(apify_jobs, pw_jobs)
        if len(merged) > self.max_items:
            merged = merged[: self.max_items]
        return merged
