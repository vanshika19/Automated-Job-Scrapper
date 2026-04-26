"""Core data models."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Company:
    name: str
    careers_url: str = ""
    linkedin_url: str = ""
    country: str = ""
    segment: str = ""

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


@dataclass
class JobPosting:
    company: str
    title: str
    url: str = ""
    location: str = ""
    department: str = ""
    description: str = ""
    source: str = ""
    posted_at: str = ""
    scraped_at: str = field(default_factory=_now_iso)

    @property
    def fingerprint(self) -> str:
        key = "|".join(
            [
                (self.company or "").strip().lower(),
                (self.title or "").strip().lower(),
                (self.url or "").strip().lower(),
            ]
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def to_row(self) -> dict:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint
        return d
