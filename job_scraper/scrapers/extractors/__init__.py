"""Per-host extractors for the Playwright scraper.

Each extractor knows how to (a) detect a URL it can handle, (b) optionally
poke the rendered page (scroll, click "Show more"), and (c) parse the final
HTML into job dicts.

The picker order is "most specific first"; `GenericExtractor` is the catch-all.
"""

from __future__ import annotations

from typing import Type

from .base import Extractor
from .ashby import AshbyExtractor
from .generic import GenericExtractor
from .greenhouse_iframe import GreenhouseIframeExtractor
from .smartrecruiters import SmartRecruitersExtractor
from .workday import WorkdayExtractor

_REGISTRY: list[Type[Extractor]] = [
    GreenhouseIframeExtractor,
    AshbyExtractor,
    WorkdayExtractor,
    SmartRecruitersExtractor,
    GenericExtractor,
]


def pick(url: str, html: str | None = None) -> Extractor:
    for cls in _REGISTRY:
        if cls.matches(url, html or ""):
            return cls()
    return GenericExtractor()


__all__ = [
    "Extractor",
    "AshbyExtractor",
    "GenericExtractor",
    "GreenhouseIframeExtractor",
    "SmartRecruitersExtractor",
    "WorkdayExtractor",
    "pick",
]
