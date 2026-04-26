"""JS-rendered career page scraper using Playwright (Chromium).

Per-host extractors live in `extractors/`. The picker chooses the best one
based on URL host first, then on signals in the rendered HTML.

Browser instance is shared across calls within a single Python process.
Install once after pip install:  `playwright install chromium`
"""

from __future__ import annotations

import logging

from ..models import Company
from .extractors import pick

LOG = logging.getLogger(__name__)


class PlaywrightScraper:
    name = "playwright"

    def __init__(self, *, wait_ms: int = 2500, headless: bool = True) -> None:
        self.wait_ms = wait_ms
        self.headless = headless
        self._pw = None
        self._browser = None

    def _ensure_browser(self):
        if self._browser is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "playwright not installed. Run `pip install playwright && playwright install chromium`."
            ) from e
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)

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

    def __del__(self) -> None:
        self.close()

    def fetch(self, company: Company) -> list[dict]:
        url = company.careers_url or ""
        if not url or "linkedin.com" in url:
            return []
        try:
            self._ensure_browser()
        except Exception as e:  # noqa: BLE001
            LOG.warning("Playwright unavailable for %s: %s", company.name, e)
            return []

        ctx = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        page = ctx.new_page()
        try:
            page.goto(url, timeout=45_000, wait_until="domcontentloaded")
            extractor = pick(url)
            try:
                extractor.prepare(page)
            except Exception as e:  # noqa: BLE001
                LOG.debug("Extractor %s prepare hook failed: %s", extractor.name, e)
            html = page.content()

            if extractor.name == "generic":
                refined = pick(url, html)
                if refined.name != "generic":
                    extractor = refined
                    try:
                        extractor.prepare(page)
                    except Exception:  # noqa: BLE001
                        pass
                    html = page.content()

            jobs = extractor.extract(html, url)
            LOG.info("playwright[%s] %s -> %d jobs", extractor.name, company.name, len(jobs))
            return jobs
        except Exception as e:  # noqa: BLE001
            LOG.warning("Playwright fetch failed for %s: %s", company.name, e)
            return []
        finally:
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass
