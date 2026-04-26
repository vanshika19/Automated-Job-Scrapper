"""Fingerprint-based deduplication helpers."""

from __future__ import annotations

from typing import Iterable, Iterator

from .models import JobPosting


def dedupe(jobs: Iterable[JobPosting]) -> Iterator[JobPosting]:
    seen: set[str] = set()
    for j in jobs:
        fp = j.fingerprint
        if fp in seen:
            continue
        seen.add(fp)
        yield j
