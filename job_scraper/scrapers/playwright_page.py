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
from .job_harvest import dedupe_jobs_by_url
from .pw_sync_runner import get_sync_playwright, run_playwright_sync

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
            self._pw = get_sync_playwright()
            self._browser = self._pw.chromium.launch(headless=self.headless)
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "playwright not installed. Run `pip install playwright && playwright install chromium`."
            ) from e

    def close(self) -> None:
        def _work() -> None:
            try:
                if self._browser is not None:
                    self._browser.close()
            except Exception:  # noqa: BLE001
                pass
            self._browser = None
            self._pw = None

        try:
            run_playwright_sync(_work)
        except Exception:  # noqa: BLE001
            pass

    def __del__(self) -> None:
        self.close()

    def fetch(self, company: Company) -> list[dict]:
        url = company.careers_url or ""
        if not url or "linkedin.com" in url:
            return []

        def _work() -> list[dict]:
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
                page.wait_for_timeout(self.wait_ms)
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

                jobs = dedupe_jobs_by_url(extractor.extract(html, url))

                # SPA boards often embed jobs in cross-origin iframes (e.g. ACKO → careers.kula.ai).
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    fu = (fr.url or "").strip()
                    if not fu or fu.startswith(("about:", "chrome-extension:")):
                        continue
                    try:
                        fh = fr.content()
                    except Exception as e:  # noqa: BLE001
                        LOG.debug("Playwright skip frame %s: %s", fu[:80], e)
                        continue
                    if len(fh) < 400:
                        continue
                    fex = pick(fu, fh)
                    try:
                        extra = fex.extract(fh, fu)
                    except Exception as e:  # noqa: BLE001
                        LOG.debug("Frame extract failed (%s): %s", fu[:80], e)
                        continue
                    jobs.extend(extra)

                jobs = dedupe_jobs_by_url(jobs)
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

        return run_playwright_sync(_work)
