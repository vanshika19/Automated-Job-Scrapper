"""Shared DDGS-based enrichment for Career Page URL + LinkedIn Jobs URL columns."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pandas as pd
from ddgs import DDGS

AGGREGATOR = (
    "linkedin.com/jobs/view",
    "linkedin.com/posts/",
    "indeed.com",
    "glassdoor.",
    "glassdoor.com",
    "monster.com",
    "ziprecruiter",
    "simplyhired",
    "google.com/search",
    "facebook.com",
    "twitter.com",
    "youtube.com",
    "careerjet.",
    "wikipedia.org",
    "cloudflare.com/careers",
    "bing.com/aclick",
)

ATS_HINT = (
    "greenhouse.io",
    "boards.greenhouse",
    "lever.co",
    "ashbyhq",
    "myworkdayjobs",
    "workday",
    "smartrecruiters",
    "rippling.com",
    "apply.workable",
    "jobs.ashbyhq",
    "teamtailor",
    "bamboohr",
    "icims.com",
)


def _norm_li(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([^/?#]+)", url, re.I)
    if not m:
        return ""
    slug = m.group(1).rstrip("/")
    return f"https://www.linkedin.com/company/{slug}/jobs/"


def _bad_career(url: str) -> bool:
    u = url.lower()
    return any(a in u for a in AGGREGATOR)


def _score_career(url: str) -> int:
    if not url or _bad_career(url):
        return -999
    u = url.lower()
    s = 0
    if any(a in u for a in ATS_HINT):
        s += 20
    if "/jobs" in u or "/careers" in u or "careers." in u:
        s += 8
    if "linkedin.com" in u:
        s -= 50
    if u.count("/") >= 3 and ("http" in u):
        s += 1
    return s


def _pick_best_career(results: list[dict]) -> str:
    best_url, best = "", -999
    for r in results:
        href = (r.get("href") or "").strip()
        if not href:
            continue
        sc = _score_career(href)
        if sc > best:
            best, best_url = sc, href.split("?")[0]
    return best_url if best > 0 else ""


def _ddgs_text(query: str, max_results: int = 12) -> list[dict]:
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            return list(DDGS().text(query, max_results=max_results))
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.6 * (attempt + 1))
    if last_err:
        print(f"DDGS failed after retries: {query!r} -> {last_err}", file=sys.stderr)
    return []


def _ctx_prefix(query_context: str) -> str:
    q = (query_context or "").strip()
    return f"{q} " if q else ""


def find_linkedin_jobs(name: str, location: str, query_context: str = "") -> str:
    cx = _ctx_prefix(query_context)
    queries = [
        f"{name} {location} {cx}site:linkedin.com/company".strip(),
        f"{name} {cx}linkedin company".strip(),
        f"{name} linkedin company",
    ]
    seen: set[str] = set()
    for q in queries:
        if q in seen:
            continue
        seen.add(q)
        for r in _ddgs_text(q, max_results=12):
            href = (r.get("href") or "").strip()
            nu = _norm_li(href)
            if nu:
                return nu
        time.sleep(0.35)
    return ""


def find_career_page(name: str, location: str, query_context: str = "") -> str:
    cx = _ctx_prefix(query_context)
    queries = [
        f"{name} {location} {cx}careers jobs".strip(),
        f"{name} {cx}official careers".strip(),
        f"{name} {cx}jobs apply".strip(),
    ]
    seen: set[str] = set()
    for q in queries:
        if q in seen:
            continue
        seen.add(q)
        rows = _ddgs_text(q, max_results=15)
        picked = _pick_best_career(rows)
        if picked:
            return picked
        time.sleep(0.35)
    return ""


def _row_location(row: pd.Series, primary: str | None, fallback: str | None) -> str:
    if primary:
        v = str(row.get(primary, "") or "").strip()
        if v:
            return v
    if fallback:
        return str(row.get(fallback, "") or "").strip()
    return ""


def enrich_workbook(
    xlsx: Path | str,
    sheet: str,
    *,
    name_col: str,
    location_col: str | None = None,
    location_fallback_col: str | None = None,
    query_context: str = "",
    checkpoint_every: int = 10,
    sleep_between_rows: float = 0.45,
) -> None:
    """Add or fill Career Page URL and LinkedIn Jobs URL; skip rows where both are set."""
    path = Path(xlsx)
    df = pd.read_excel(path, sheet_name=sheet)
    if name_col not in df.columns:
        raise KeyError(f"Missing column {name_col!r} in {path} sheet {sheet!r}")

    if "Career Page URL" not in df.columns:
        df["Career Page URL"] = ""
    if "LinkedIn Jobs URL" not in df.columns:
        df["LinkedIn Jobs URL"] = ""

    for col in ("Career Page URL", "LinkedIn Jobs URL"):
        df[col] = df[col].fillna("").astype(str).replace("nan", "")

    total = len(df)
    for i, row in df.iterrows():
        name = str(row[name_col]).strip()
        loc = _row_location(row, location_col, location_fallback_col)

        if str(row.get("Career Page URL", "")).strip() and str(row.get("LinkedIn Jobs URL", "")).strip():
            continue

        print(f"[{i + 1}/{total}] {name} ({loc}) ...", flush=True)
        if not str(row.get("Career Page URL", "")).strip():
            df.at[i, "Career Page URL"] = find_career_page(name, loc, query_context)
        if not str(row.get("LinkedIn Jobs URL", "")).strip():
            df.at[i, "LinkedIn Jobs URL"] = find_linkedin_jobs(name, loc, query_context)

        if (i + 1) % checkpoint_every == 0:
            df.to_excel(path, sheet_name=sheet, index=False)
            print(f"  checkpoint saved ({i + 1} rows)", flush=True)
        time.sleep(sleep_between_rows)

    df.to_excel(path, sheet_name=sheet, index=False)
    print("Done. Saved:", path, flush=True)
