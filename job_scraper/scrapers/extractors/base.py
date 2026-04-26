"""Base class for per-host Playwright extractors."""

from __future__ import annotations

from typing import Any


class Extractor:
    """Strategy interface used by `PlaywrightScraper`."""

    name: str = "generic"
    wait_ms: int = 2500

    @classmethod
    def matches(cls, url: str, html: str = "") -> bool:  # pragma: no cover - override
        return False

    def prepare(self, page: Any) -> None:
        """Hook for pre-extraction interactions (scroll, click 'Load more', etc.)."""
        try:
            page.wait_for_load_state("networkidle", timeout=self.wait_ms)
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(self.wait_ms)

    def extract(self, html: str, base_url: str) -> list[dict]:  # pragma: no cover - override
        return []
