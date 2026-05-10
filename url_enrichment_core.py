"""DDGS-based enrichment for Career Page URL + LinkedIn Jobs URL columns.

Now with 4-layer verification on every candidate:

    1. Aggregator blocklist (expanded — covers Indian aggregators)
    2. Domain belongs to the company  (or URL is on a known ATS host with a
       company-matching slug, e.g. boards.greenhouse.io/<slug>/jobs/...)
    3. URL fetches with 2xx
    4. Page content actually looks like a careers page
       ("careers", "open positions", "join us", "we're hiring", ...)

Before falling back to a noisy DDGS search, we deterministically probe the
company's official domain at standard career paths (`/careers`, `careers.<domain>`,
`jobs.<domain>`, ...). That catches well-organised companies — e.g. Cred resolves
to `https://careers.cred.club/` without needing to trust search rankings.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd
import requests
from ddgs import DDGS

# ---------------------------------------------------------------------------
# Blocklists
# ---------------------------------------------------------------------------

GLOBAL_AGGREGATORS = (
    "linkedin.com/jobs/view",
    "linkedin.com/posts/",
    # Commonly mis-ranked “review” / unrelated companies with similar names
    "pissedconsumer.com",
    "chimeplc.com",
    "sofistadium.com",
    "indeed.com",
    "glassdoor.",
    "monster.com",
    "monster.in",
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
    "jora.com",
    "trovit.com",
    "talent.com",
    "neuvoo.com",
    "careerbuilder.com",
    "jobrapido.com",
    "jobomas.com",
)

# India-flavoured aggregators that the live test surfaced for fintech rows.
INDIAN_AGGREGATORS = (
    "freshersworld.com",
    "careermine.com",
    "jobsforcommerce.com",
    "jobs4fresher.com",
    "naukri.com",
    "shine.com",
    "hirist.com",
    "instahyre.com",
    "foundit.in",
    "timesjobs.com",
    "iimjobs.com",
    "cutshort.io",
    "apna.co",
    "internshala.com",
    "placementindia.com",
    "jobsforher.com",
    "ambitionbox.com",
    "kitjob.in",
    "yourstory.com",
    "expertia.ai",
    "shiksha.com",
    "pissedconsumer.com",
    "builtin.com",
    "builtinnyc.com",
    "builtintoronto.com",
    "ycombinator.com",
    "wellfound.com",
    "angel.co",
    "bayt.com",
    "zhihu.com",
    "quora.com",
)

AGGREGATOR = GLOBAL_AGGREGATORS + INDIAN_AGGREGATORS

# Real ATS hosts (these can be cross-domain from the company's main site and
# still legitimately host its jobs).
ATS_HOSTS = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "jobs.smartrecruiters.com",
    "myworkdayjobs.com",
    "apply.workable.com",
    "rippling.com",
    "teamtailor.com",
    "bamboohr.com",
    "icims.com",
    "hire.trakstar.com",
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
    "teamtailor",
    "bamboohr",
    "icims.com",
    "hire.trakstar",
)

# Strip only true legal-form suffixes; keep brand-part words like "Labs" or
# "Tech" because they discriminate between companies (Pine Labs vs Pine Inc).
_NAME_STOPWORDS = {
    "the", "and", "of", "a", "an",
    "ltd", "limited", "inc", "incorporated", "llc",
    "co", "corp", "corporation", "company", "group", "holdings",
    "pvt", "private", "public", "plc", "ag", "sa", "bv", "gmbh",
}

# Generic public-suffix-ish labels we should NOT match against company tokens.
_TLD_LABELS = {
    "com", "co", "in", "io", "ai", "net", "org", "club", "app", "tech",
    "dev", "page", "site", "online", "global", "cloud", "us", "uk", "eu",
}

CAREER_KEYWORDS = (
    "careers",
    "career",
    "we're hiring",
    "we are hiring",
    "open positions",
    "open roles",
    "current openings",
    "current opportunities",
    "job openings",
    "join us",
    "join our team",
    "work with us",
    "apply now",
    "view jobs",
    "browse jobs",
    "all jobs",
    "see open jobs",
    "view all roles",
)

# ---------------------------------------------------------------------------
# Pure helpers (no network)
# ---------------------------------------------------------------------------


def _company_tokens(name: str) -> set[str]:
    """Significant tokens from a company name for domain-match checks.

    Includes the concatenation of all words too so "Pine Labs" matches
    "pinelabs.com" and "Pay U" matches "payu.com".
    """
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", name or "").lower()
    words = [w for w in cleaned.split() if len(w) >= 2 and w not in _NAME_STOPWORDS]
    if not words:
        return set()
    tokens = set(words)
    if len(words) > 1:
        tokens.add("".join(words))
    return tokens


def _registrable_host(url: str) -> str:
    """Best-effort `registrable` host: drop common subdomain prefixes."""
    host = urlparse(url).netloc.lower()
    return re.sub(r"^(www\.|careers\.|jobs\.|hire\.|apply\.|talent\.|join\.)", "", host)


def _is_ats_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host.endswith(h) or h in host for h in ATS_HOSTS)


def _ats_slug(url: str) -> str:
    """First path component (the company slug on most ATS hosts)."""
    path = urlparse(url).path.lstrip("/")
    return path.split("/", 1)[0].lower() if path else ""


def _domain_matches_company(url: str, name: str) -> bool:
    """True if the URL clearly belongs to the company.

    For company-owned domains: any token from the company name appears in the
    registrable host. For ATS-hosted boards: the company slug in the URL path
    overlaps the company tokens.
    """
    if not url or not name:
        return False
    tokens = _company_tokens(name)
    if not tokens:
        return False
    if _is_ats_host(url):
        slug = _ats_slug(url)
        if not slug:
            return False
        return any(tok in slug or slug in tok for tok in tokens)

    host = _registrable_host(url)
    if not host:
        return False
    labels = [lbl for lbl in host.split(".") if lbl and lbl not in _TLD_LABELS]
    for tok in tokens:
        for label in labels:
            if tok == label:
                return True
            # Substring overlap is only safe for longer tokens; 2-3 char tokens
            # too easily match unrelated hosts (e.g. "aim" → "claim").
            if len(tok) >= 4 and (tok in label or label in tok):
                return True
    return False


def _is_aggregator(url: str) -> bool:
    u = (url or "").lower()
    return any(a in u for a in AGGREGATOR)


def _has_career_signals(html: str) -> bool:
    if not html:
        return False
    text = html.lower()
    return sum(1 for kw in CAREER_KEYWORDS if kw in text) >= 1


def _score_career(url: str) -> int:
    """URL-shape score; combined with verification in `find_career_page`."""
    if not url or _is_aggregator(url):
        return -999
    u = url.lower()
    s = 0
    if any(a in u for a in ATS_HINT):
        s += 20
    if "/careers" in u or "careers." in u:
        s += 10
    if "/jobs" in u or "jobs." in u:
        s += 8
    if "linkedin.com" in u:
        s -= 50
    if u.count("/") >= 3 and u.startswith("http"):
        s += 1
    return s


def _norm_li(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/([^/?#]+)", url, re.I)
    if not m:
        return ""
    slug = m.group(1).rstrip("/")
    return f"https://www.linkedin.com/company/{slug}/jobs/"


# ---------------------------------------------------------------------------
# HTTP layer (split out so tests can monkeypatch without touching the network)
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _http_get(url: str, timeout: float = 8.0) -> tuple[int, str] | None:
    """Single-shot GET with a sane User-Agent. Returns (status, text) or None."""
    try:
        r = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en"},
            timeout=timeout,
            allow_redirects=True,
        )
        return r.status_code, r.text or ""
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Verification — the new core
# ---------------------------------------------------------------------------


def verify_career_url(url: str, name: str, *, fetch: bool = True) -> bool:
    """Run all four checks on a candidate career URL.

    Set `fetch=False` to skip the network round-trip (useful for fast bulk
    pre-filtering, but you'll want to verify with `fetch=True` before trusting).
    """
    if not url or _is_aggregator(url):
        return False
    if not _domain_matches_company(url, name):
        return False
    if not fetch:
        return True
    res = _http_get(url)
    if res is None:
        return False
    status, html = res
    if status >= 400:
        return False
    return _has_career_signals(html)


# ---------------------------------------------------------------------------
# Official-domain probing
# ---------------------------------------------------------------------------


def _candidate_official_urls(results: Iterable[dict], name: str) -> list[str]:
    """Pick result URLs whose registrable host plausibly belongs to the company."""
    out: list[str] = []
    seen: set[str] = set()
    for r in results:
        href = (r.get("href") or "").strip()
        if not href or _is_aggregator(href):
            continue
        if _is_ats_host(href):
            continue
        host = _registrable_host(href)
        if not host or host in seen:
            continue
        if _domain_matches_company(href, name):
            seen.add(host)
            out.append(f"https://{host}/")
    return out


def find_official_domain(name: str, location: str = "", query_context: str = "") -> str:
    """Best guess of the company's home page (e.g. 'https://cred.club/')."""
    cx = _ctx_prefix(query_context)
    queries = [
        f"{name} {location} {cx}official site".strip(),
        f"{name} {cx}official website".strip(),
        f"{name} home page",
    ]
    seen: set[str] = set()
    for q in queries:
        if q in seen:
            continue
        seen.add(q)
        rows = _ddgs_text(q, max_results=10)
        for url in _candidate_official_urls(rows, name):
            res = _http_get(url)
            if res is None:
                continue
            status, _ = res
            if 200 <= status < 400:
                return url
        time.sleep(0.3)
    return ""


def _standard_career_paths(home_url: str) -> list[str]:
    """Generate likely career-page URLs from a company's home URL."""
    parsed = urlparse(home_url if home_url.startswith("http") else f"https://{home_url}")
    host = parsed.netloc.lower()
    if not host:
        return []
    bare = re.sub(r"^www\.", "", host)
    return [
        f"https://careers.{bare}/",
        f"https://jobs.{bare}/",
        f"https://www.{bare}/careers/",
        f"https://www.{bare}/careers",
        f"https://www.{bare}/jobs/",
        f"https://www.{bare}/jobs",
        f"https://{bare}/careers/",
        f"https://{bare}/careers",
        f"https://{bare}/jobs/",
        f"https://{bare}/jobs",
        f"https://www.{bare}/about/careers/",
        f"https://www.{bare}/company/careers/",
        f"https://www.{bare}/join-us/",
        f"https://www.{bare}/work-with-us/",
    ]


def probe_official_career_paths(home_url: str, name: str) -> str:
    """Try standard career paths on the official domain; return first verified."""
    seen: set[str] = set()
    for url in _standard_career_paths(home_url):
        if url in seen:
            continue
        seen.add(url)
        if verify_career_url(url, name, fetch=True):
            return url
    return ""


# ---------------------------------------------------------------------------
# DDGS layer
# ---------------------------------------------------------------------------


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


def _verified_career_from_search(name: str, location: str, query_context: str) -> str:
    """Run DDGS searches; for each candidate, score, then verify (network)."""
    cx = _ctx_prefix(query_context)
    queries = [
        f"{name} {location} {cx}careers jobs".strip(),
        f"{name} {cx}official careers".strip(),
        f"{name} {cx}jobs apply".strip(),
        f'"{name}" careers page'.strip(),
    ]
    seen_url: set[str] = set()
    candidates: list[tuple[int, str]] = []
    for q in queries:
        for r in _ddgs_text(q, max_results=15):
            href = (r.get("href") or "").strip().split("?")[0]
            if not href or href in seen_url:
                continue
            seen_url.add(href)
            sc = _score_career(href)
            if sc <= 0:
                continue
            if not (_domain_matches_company(href, name) or _is_ats_host(href)):
                continue
            candidates.append((sc, href))
        time.sleep(0.3)

    candidates.sort(reverse=True)
    for _, url in candidates[:6]:
        if verify_career_url(url, name, fetch=True):
            return url
    return ""


# ---------------------------------------------------------------------------
# Public API (used by enrich_*.py and tests)
# ---------------------------------------------------------------------------


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


def find_career_page(name: str, location: str = "", query_context: str = "") -> str:
    """Verified career-page lookup. Returns "" if nothing passes verification."""
    home = find_official_domain(name, location, query_context)
    if home:
        url = probe_official_career_paths(home, name)
        if url:
            return url

    return _verified_career_from_search(name, location, query_context)


# ---------------------------------------------------------------------------
# Workbook enrichment
# ---------------------------------------------------------------------------


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
    reverify: bool = False,
    segment_filter: str | None = None,
    segment_col: str = "Sub-Segment",
) -> None:
    """Add or fill Career Page URL and LinkedIn Jobs URL.

    Default (`reverify=False`) preserves the historical behaviour: skip rows
    that already have both URLs.

    With `reverify=True`, every existing Career Page URL is re-checked; if it
    fails verification (aggregator, wrong domain, dead link, no career signals)
    the cell is cleared and re-populated via `find_career_page`. LinkedIn URLs
    are only filled if missing — they're a structured slug so re-verification
    is rarely needed.

    With ``segment_filter`` set (e.g. ``"BFSI FinTech list 2025"``), **only**
    rows whose ``segment_col`` matches are touched. For those rows, **only
    blank** Career / LinkedIn cells are filled — existing URLs are never
    overwritten and ``reverify`` is ignored. All other rows are left unchanged
    (safe for already-corrected companies).
    """
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
    replaced = 0
    processed = 0

    if segment_filter is not None:
        if segment_col not in df.columns:
            raise KeyError(f"--only-segment requires column {segment_col!r} in {path}")
        if reverify:
            print("Note: reverify is disabled when --only-segment is used.", flush=True)
            reverify = False

        want = segment_filter.strip()
        eligible = sum(
            1
            for _, row in df.iterrows()
            if str(row.get(segment_col, "") or "").strip() == want
        )
        print(
            f"Segment filter: {want!r} — {eligible} row(s), fill blanks only; other rows unchanged.",
            flush=True,
        )

        for i, row in df.iterrows():
            if str(row.get(segment_col, "") or "").strip() != want:
                continue

            name = str(row[name_col]).strip()
            if not name:
                continue
            loc = _row_location(row, location_col, location_fallback_col)
            existing_career = str(row.get("Career Page URL", "")).strip()
            existing_li = str(row.get("LinkedIn Jobs URL", "")).strip()

            if existing_career and existing_li:
                continue

            need_career = not existing_career
            need_li = not existing_li
            processed += 1
            print(f"[{processed}/{eligible}] {name} ({loc}) ...", flush=True)

            if need_career:
                new_url = find_career_page(name, loc, query_context)
                df.at[i, "Career Page URL"] = new_url
                print(f"    career → {new_url or '(none)'}", flush=True)
            if need_li:
                df.at[i, "LinkedIn Jobs URL"] = find_linkedin_jobs(name, loc, query_context)
                print(f"    linkedin → {df.at[i, 'LinkedIn Jobs URL'] or '(none)'}", flush=True)

            if processed % checkpoint_every == 0:
                df.to_excel(path, sheet_name=sheet, index=False)
                print(f"  checkpoint saved ({processed} segment rows)", flush=True)
            time.sleep(sleep_between_rows)

        df.to_excel(path, sheet_name=sheet, index=False)
        print(f"Done. Saved: {path} ({processed} segment row(s) updated)", flush=True)
        return

    for i, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name:
            continue
        loc = _row_location(row, location_col, location_fallback_col)
        existing_career = str(row.get("Career Page URL", "")).strip()
        existing_li = str(row.get("LinkedIn Jobs URL", "")).strip()

        career_ok = bool(existing_career) and (
            verify_career_url(existing_career, name) if reverify else True
        )
        if reverify and existing_career and not career_ok:
            print(f"  ↪ rejected {existing_career!r} for {name!r}", flush=True)
            replaced += 1

        if career_ok and existing_li and not reverify:
            continue

        print(f"[{i + 1}/{total}] {name} ({loc}) ...", flush=True)
        if not career_ok:
            new_url = find_career_page(name, loc, query_context)
            df.at[i, "Career Page URL"] = new_url
            print(f"    career → {new_url or '(none)'}", flush=True)
        if not existing_li:
            df.at[i, "LinkedIn Jobs URL"] = find_linkedin_jobs(name, loc, query_context)

        if (i + 1) % checkpoint_every == 0:
            df.to_excel(path, sheet_name=sheet, index=False)
            print(f"  checkpoint saved ({i + 1} rows)", flush=True)
        time.sleep(sleep_between_rows)

    df.to_excel(path, sheet_name=sheet, index=False)
    suffix = f", replaced {replaced} bad URL(s)" if reverify else ""
    print(f"Done. Saved: {path}{suffix}", flush=True)
