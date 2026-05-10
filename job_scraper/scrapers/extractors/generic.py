"""Catch-all extractor: anchor harvesting on the rendered HTML."""

from __future__ import annotations

from .base import Extractor
from ..job_harvest import harvest_job_links

_PW_TITLE_MAX = 160


class GenericExtractor(Extractor):
    name = "generic"

    @classmethod
    def matches(cls, url: str, html: str = "") -> bool:
        return True  # always matches as fallback

    def extract(self, html: str, base_url: str) -> list[dict]:
        return harvest_job_links(
            html,
            base_url,
            max_title_len=_PW_TITLE_MAX,
            source="playwright:generic",
        )
