"""Isolate Playwright sync_api on one worker thread.

The sync Playwright driver raises if ``asyncio`` has a running loop on the calling
thread (seen with newer Python / certain hosts). Serializing all sync Playwright
calls through a single ``ThreadPoolExecutor`` worker avoids that and keeps browser
access thread-safe for our scrapers.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

_T = TypeVar("_T")

_executor: ThreadPoolExecutor | None = None

# One sync Playwright driver per process on the worker thread (Playwright forbids
# multiple sync_playwright().start() calls on the same thread — otherwise we get
# "Sync API inside the asyncio loop" when e.g. LinkedIn runs after PlaywrightScraper).
_sync_pw = None


def _executor_singleton() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job-scraper-pw")
    return _executor


def run_playwright_sync(work: Callable[[], _T]) -> _T:
    """Run ``work`` on the dedicated Playwright thread."""
    return _executor_singleton().submit(work).result()


def get_sync_playwright():
    """Return the shared sync Playwright driver; call only inside ``run_playwright_sync``."""
    global _sync_pw
    if _sync_pw is None:
        from playwright.sync_api import sync_playwright

        _sync_pw = sync_playwright().start()
    return _sync_pw


def stop_shared_playwright() -> None:
    """Stop the shared driver after every per-scraper browser has been closed."""

    def _work() -> None:
        global _sync_pw
        if _sync_pw is None:
            return
        try:
            _sync_pw.stop()
        except Exception:  # noqa: BLE001
            pass
        _sync_pw = None

    try:
        run_playwright_sync(_work)
    except Exception:  # noqa: BLE001
        pass
