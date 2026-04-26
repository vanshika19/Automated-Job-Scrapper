"""Rule-based filters for postings."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator

from .models import JobPosting


@dataclass
class FilterRules:
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()

    @staticmethod
    def _ci_search(text: str, terms: Iterable[str]) -> bool:
        if not terms:
            return False
        pat = re.compile("|".join(re.escape(t) for t in terms), re.I)
        return bool(pat.search(text or ""))

    def matches(self, job: JobPosting) -> bool:
        haystack = " ".join([job.title, job.department, job.description])
        if self.include and not self._ci_search(haystack, self.include):
            return False
        if self.exclude and self._ci_search(haystack, self.exclude):
            return False
        if self.locations and not self._ci_search(job.location, self.locations):
            return False
        return True


def apply(jobs: Iterable[JobPosting], rules: FilterRules | None) -> Iterator[JobPosting]:
    if rules is None:
        yield from jobs
        return
    for j in jobs:
        if rules.matches(j):
            yield j
