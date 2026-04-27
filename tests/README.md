# Tests

```
tests/
├── conftest.py                       # fixtures + adds repo root to sys.path
├── test_career_page_scraper.py       # unit tests for CareerPageScraper (mocked HTTP)
└── test_career_page_live.py          # live test: real fintech career pages (opt-in)
```

## One-time setup

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt        # adds pytest on top of the runtime deps
```

## Run unit tests (fast, no network)

```bash
pytest tests/ -m "not live" -v
```

This runs in ~1 s and does not touch the internet. Safe for CI / pre-commit.

## Run live tests against the fintech registry

These actually hit real career pages over the internet, so they're skipped by
default. Opt in with `-m live`:

```bash
pytest tests/test_career_page_live.py -m live -s
```

`-s` keeps the per-company yield report visible. Sample output:

```
=== CareerPageScraper live yield ===
  Stripe                              0  (https://stripe.com/jobs)
  Plaid                               17  (https://plaid.com/careers/)
  Brex                                3   (https://www.brex.com/careers)
  ...
  -- 32 jobs from 8 companies
```

Tweak how many companies are tried with `LIVE_LIMIT`:

```bash
LIVE_LIMIT=20 pytest tests/test_career_page_live.py -m live -s
```

The live test deliberately **only** picks companies whose `careers_url` is **not**
hosted on a known ATS (Greenhouse, Lever, Ashby, Workday, SmartRecruiters) — the
ATS pages have their own scraper (`ats.py`) and the JS-rendered ones need
Playwright. This keeps the live test focused on the BeautifulSoup path.

## Adding new tests

- Put unit tests next to their target's name (`test_<module>.py`).
- Use the `stub_http_get` fixture to inject HTML without touching the network.
- Mark tests that need real network access with `@pytest.mark.live` so they
don't run by default.

