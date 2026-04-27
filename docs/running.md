# Running the job scraper end-to-end

There are two supported ways to run this project. Pick the one that matches your
goal:

- **Path A — Docker Compose** (full stack: Postgres + FastAPI + scraper cron
worker + React dashboard). Production-shaped. **Use this to actually operate
the scraper.**
- **Path B — Local Python venv + Vite dev server** (SQLite, no scheduler). No
Docker needed. **Use this for fast inner-loop development.**

The bottom of this doc has a side-by-side comparison and a deeper "what happens
when you run each command" breakdown.

---

## TL;DR

```bash
# Path A — full stack
cd ~/Applications/job-scrapper
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # → put in .env as API_TOKEN
docker compose up -d --build
docker compose exec scraper python -m job_scraper scrape --source ats
open http://localhost:8080
docker compose logs -f scraper           # watch the cron schedule fire
```

```bash
# Path B — local Python only (no scheduler)
cd ~/Applications/job-scrapper
source .venv/bin/activate
export DATABASE_URL=sqlite:///jobs.db
export STORAGE_AUTO_CREATE=1
export API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "API_TOKEN=$API_TOKEN"
python -m job_scraper init-db
python -m job_scraper scrape --source ats
python -m job_scraper serve --host 0.0.0.0 --port 8000   # leave running
# in a second terminal:
cd frontend && npm install && npm run dev                # opens on :5173
```

---

## Path A — Docker Compose (recommended)

This is the canonical way to run everything together. You get the same image
and topology you'd deploy to a server.

### A0. Prerequisites

- macOS / Linux with Docker Desktop running. Verify with:
  ```bash
  docker --version
  docker compose version
  docker info --format '{{.ServerVersion}}'
  ```
  If `docker info` says "Cannot connect to the Docker daemon", launch the
  Docker Desktop app and wait for the whale icon to settle.
- ~6 GB free disk space (Postgres + Playwright base image + node deps).

### A1. Create your local `.env`

```bash
cd ~/Applications/job-scrapper
cp .env.example .env
```

Then **set `API_TOKEN`** to a strong random value — both the API and the
frontend require it. Generate one:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Open `.env` in your editor and paste:

```
API_TOKEN=<the_string_you_just_generated>
```

Leave the rest of the defaults alone for now (the Postgres credentials and
`DATABASE_URL` already match what compose expects). `.env` is gitignored so
your secrets stay local.

### A2. Build images and start the stack

```bash
docker compose up -d --build
```

What this does, step by step:

1. `**db` (Postgres 16)** — pulls the alpine image, creates the `jobs`
  database, mounts a named volume `db_data` for persistence, and exposes a
   healthcheck (`pg_isready`).
2. `**api` (built from `Dockerfile`)** — installs the Python deps **without
  Playwright** to keep the image slim, copies `job_scraper/`, `migrations/`,
   and `alembic.ini`, then on each container start runs:
  - `wait-for-db.sh` — blocks until Postgres is reachable.
  - `alembic upgrade head` — applies any pending schema migrations.
  - `python -m job_scraper init-db` — loads companies from the four
  `*_structured.xlsx` registries (skipped silently if already present).
  - `uvicorn job_scraper.api:app --host 0.0.0.0 --port 8000`.
3. `**scraper` (built from `Dockerfile.scraper`)** — same migration + `init-db`
  bootstrap, but uses the heavier `mcr.microsoft.com/playwright/python` base
   image (Chromium pre-installed) so JS-rendered pages work. Then it launches
   `supercronic /etc/crontab`, which keeps running and fires jobs based on
   `docker/crontab`.
4. `**frontend` (built from `frontend/Dockerfile`)** — multi-stage build:
  `node:20` builds the Vite/React app, then nginx serves the static
   `dist/` and reverse-proxies `/api/`* to the `api` container.

After ~3–5 minutes (first build only) all four containers are up. Check:

```bash
docker compose ps
```

Expected: every row says `running` and `healthy` (the `db` healthcheck).

### A3. Trigger a real scrape (optional but recommended)

The cron worker would eventually run on its own schedule, but to see data in
the UI immediately:

```bash
docker compose exec scraper python -m job_scraper scrape --source ats
```

That hits the public Greenhouse + Lever JSON APIs for every company that has a
detected ATS slug, normalises the postings, dedups them, and upserts into
Postgres. Typical first run: 30–60 s, a few hundred jobs.

You can also run the slower sources on demand:

```bash
docker compose exec scraper python -m job_scraper scrape --source career
docker compose exec scraper python -m job_scraper scrape --source playwright
```

### A4. Open the dashboard

Visit **[http://localhost:8080](http://localhost:8080)**.

The first request returns 401 because the API requires a bearer token. The UI
detects this and pops a token dialog — paste the same `API_TOKEN` you put in
`.env`. It's saved to `localStorage`, so you only do this once per browser.

You'll see two tabs:

- **Jobs** — full-text search, filter by source / location, links out to each
posting.
- **Match** — upload a PDF or text resume; the matcher embeds it (locally with
sentence-transformers, or via OpenAI if `OPENAI_API_KEY` is set) and ranks
the open jobs by cosine similarity.

The header shows global stats from `/api/stats` (companies, total jobs, jobs
per source).

### A5. Watch the schedule run

`supercronic` logs every cron tick to stdout, so:

```bash
docker compose logs -f scraper
```

Sample output:

```
scraper-1  | level=info msg="read job=0 schedule=\"0 */6 * * *\" command=\"/usr/local/bin/scrape.sh ats\""
scraper-1  | level=info msg="starting iteration=1 job.command=\"/usr/local/bin/scrape.sh ats\""
scraper-1  | [2026-04-26T13:30:02+00:00] scrape source=ats
scraper-1  | INFO:job_scraper.pipeline:scraped 47 jobs from 12 companies via ats
scraper-1  | level=info msg="job succeeded" iteration=1 ...
```

The schedule (UTC, defined in `docker/crontab`) is:


| Cron            | Job           | Source                            |
| --------------- | ------------- | --------------------------------- |
| `0 */6 * * *`   | every 6 hours | `ats` (Greenhouse + Lever JSON)   |
| `30 6,18 * * *` | 06:30 & 18:30 | `career` (generic HTML scrape)    |
| `15 3 * * *`    | 03:15 daily   | `playwright` (JS-rendered pages)  |
| `0 4 * * *`     | 04:00 daily   | export `/app/data/jobs_open.xlsx` |


To change the cadence, edit `docker/crontab` and rebuild:

```bash
docker compose up -d --build scraper
```

### A6. Other useful commands while it runs

```bash
docker compose logs -f api          # FastAPI request logs
docker compose logs -f frontend     # nginx access logs

# Quick API smoke test
TOKEN=$(grep ^API_TOKEN= .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/stats | python3 -m json.tool

# Inspect Postgres directly
docker compose exec db psql -U jobs -d jobs -c \
  "select source, count(*) from jobs group by 1 order by 2 desc;"

# Pull the daily Excel export onto your Mac
docker compose cp scraper:/app/data/jobs_open.xlsx ./jobs_open.xlsx

# Stop everything (DB volume retained)
docker compose down

# Stop AND wipe DB + exports
docker compose down -v
```

### A7. Updating the code

After editing Python or React sources, rebuild the affected service(s):

```bash
docker compose up -d --build api          # backend changes
docker compose up -d --build scraper      # scraper / extractors / cron
docker compose up -d --build frontend     # React UI
```

`db` never needs rebuilding.

---

## Path B — Local Python venv (fast dev loop)

Use this when you're iterating on Python or React code and don't want
container build times in the way. There is **no scheduler** in this mode — you
re-run `scrape` manually whenever you want fresh data.

### B1. Backend

```bash
cd ~/Applications/job-scrapper
source .venv/bin/activate              # your existing venv
pip install -r requirements.txt        # if anything was added since you last installed

# SQLite is fine for dev; STORAGE_AUTO_CREATE lets SQLAlchemy create the schema
# without needing alembic.
export DATABASE_URL=sqlite:///jobs.db
export STORAGE_AUTO_CREATE=1
export API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "API_TOKEN=$API_TOKEN"            # paste this into the UI later

# One-time: load companies from the four registries.
python -m job_scraper init-db

# Pull jobs once.
python -m job_scraper scrape --source ats
python -m job_scraper scrape --source career
# Playwright source needs a one-time `playwright install chromium` first.

# Start the API. Leave this running.
python -m job_scraper serve --host 0.0.0.0 --port 8000
```

The API is now at `http://localhost:8000/api/...`.

### B2. Frontend (in a second terminal)

```bash
cd ~/Applications/job-scrapper/frontend
npm install                            # first time only
npm run dev                            # Vite dev server on :5173
```

Open **[http://localhost:5173](http://localhost:5173)**. Vite proxies `/api/`* to FastAPI on `:8000`, so
the same auth flow applies — paste the `API_TOKEN` you printed earlier when
prompted.

Hot reload is live: edits to `src/`** reflect in the browser within seconds.

### B3. Re-running the scraper

Just re-run the same `python -m job_scraper scrape ...` command from B1
whenever you want fresh data. The matcher (`Match` tab) re-embeds against
whatever's currently in `jobs.db`.

### B4. (Optional) Schedule it without Docker

If you want a cron-style cadence without containers, see `docs/scheduler.md` —
it has copy-paste recipes for `crontab`, macOS `launchd`, and AWS
EventBridge → Fargate.

---

## Path A vs Path B — which should I use?


|                                | Path A — Docker Compose                               | Path B — Local Python                                 |
| ------------------------------ | ----------------------------------------------------- | ----------------------------------------------------- |
| **Database**                   | Postgres 16 (in `db_data` volume)                     | SQLite file (`jobs.db`)                               |
| **Schema management**          | Alembic migrations on container start                 | `STORAGE_AUTO_CREATE=1` lets SQLAlchemy create tables |
| **Scheduler**                  | `supercronic` runs the schedule in `docker/crontab`   | None — you run `scrape` manually                      |
| **Playwright**                 | Pre-installed in the `scraper` image                  | You'd run `playwright install chromium` yourself      |
| **Frontend**                   | `nginx` serving the production Vite build             | `vite dev` with hot reload                            |
| **API URL**                    | `http://localhost:8000`                               | `http://localhost:8000`                               |
| **Dashboard URL**              | `http://localhost:8080`                               | `http://localhost:5173`                               |
| **Auth**                       | Bearer token from `.env` `API_TOKEN`                  | Bearer token from the env var you set                 |
| **Startup time (warm)**        | ~10 s                                                 | ~2 s for API, ~5 s for Vite                           |
| **Startup time (first build)** | ~3–5 min                                              | ~1 min (`pip` + `npm install`)                        |
| **Disk footprint**             | ~3 GB images + Postgres data                          | ~500 MB venv + SQLite file                            |
| **Best for**                   | Operating the scraper, demos, anything "always-on"    | Iterating on code, debugging, single-run experiments  |
| **Closest to production**      | Yes — same Dockerfiles, same Postgres, same scheduler | No — SQLite + dev server only                         |


**Rule of thumb:**

- Editing code? Path B.
- Want jobs to keep refreshing themselves? Path A.
- Showing it to someone? Path A.

The two are interoperable: you can develop with Path B (SQLite) and switch to
Path A (Postgres) when ready by just running `docker compose up -d --build`.
The Excel registries are the source of truth for companies, so both paths end
up with the same set of companies after `init-db`.

---

## End-to-end breakdown — what happens when you run a scrape

This is the data flow regardless of which path you chose:

1. **Registry load** (`job_scraper/registry.py`) — reads
  `fintech_companies_structured.xlsx`,
   `family_offices_structured.xlsx`,
   `vc_companies_structured.xlsx`,
   `pe_companies_structured.xlsx`. Normalises columns into `Company` dataclass
   instances (slug, segment, careers_url, linkedin_url).
2. **Pipeline orchestration** (`job_scraper/pipeline.py`) — for each requested
  `--source`, picks the right scraper from `SOURCE_REGISTRY`:
  - `ats`        → `scrapers/ats.py` (Greenhouse + Lever JSON APIs)
  - `career`     → `scrapers/career_page.py` (BeautifulSoup anchor harvesting)
  - `playwright` → `scrapers/playwright_page.py` + per-host extractors in
   `scrapers/extractors/` (Ashby / Workday / SmartRecruiters /
   Greenhouse-iframe / generic)
  - `linkedin`   → `scrapers/linkedin.py` (stub; uses Apify when `APIFY_TOKEN`)
3. **Per-company loop** — for every company with a relevant URL the scraper
  yields raw dict rows. `parser.py` normalises them into `JobPosting`
   instances with absolute URLs and cleaned text.
4. **Filter + dedup** — `filters.py` drops postings that don't match the
  include/exclude/location rules; `dedup.py` collapses duplicates by SHA256
   of `(company_slug, title, location, url)`.
5. **Storage upsert** (`job_scraper/storage.py` + `db.py`) — opens a SQLAlchemy
  session against `DATABASE_URL`. Uses dialect-aware `INSERT ... ON CONFLICT`
   so the same code works on SQLite and Postgres. Each posting gets
   `first_seen_at` (insert) / `last_seen_at` (update). Old postings whose
   `last_seen_at` is older than the cutoff get marked `status='closed'`.
6. **API surface** (`job_scraper/api.py`) — FastAPI endpoints query the same
  tables: `/api/jobs` (filterable), `/api/companies`, `/api/stats`,
   `/api/match` (resume upload). All except `/api/health` require the bearer
   token from `auth.py`.
7. **Matching** (`job_scraper/matching.py`) — when a resume hits `/api/match`,
  `resume.py` extracts text (pdfplumber for PDFs), the embedder
   (sentence-transformers locally, OpenAI if key is set) embeds resume + jobs,
   and we return the top-N by cosine similarity.
8. **Frontend** (`frontend/src/`*) — `JobsView.tsx` calls `/api/jobs`,
  `MatchView.tsx` POSTs the resume to `/api/match`, `App.tsx` shows global
   stats and handles the 401 → token dialog flow via `auth.ts`.

In Path A the same flow runs inside the `scraper` container on a cron, with
Postgres as the destination and the React build served by nginx. In Path B
the flow runs in your venv against `jobs.db`, served by `vite dev`.

---

## Where to look when something is wrong


| Symptom                                      | First thing to check                                                                                                                                       |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Dashboard loads but says "401 Unauthorized"  | `API_TOKEN` in `.env` matches what you pasted in the UI. Clear it via the cog → "Sign out" and re-enter.                                                   |
| Dashboard is empty                           | Did you actually run a scrape? `docker compose exec scraper python -m job_scraper scrape --source ats`.                                                    |
| `docker compose up` fails on the `api` build | `docker compose build api --no-cache` and read the trace. Most failures are pip resolution issues.                                                         |
| Cron jobs don't seem to run                  | `docker compose logs scraper` — if you don't see `level=info msg="read job=...` lines, supercronic didn't pick up `/etc/crontab`.                          |
| Postgres "role does not exist"               | `docker compose down -v && docker compose up -d --build` rebuilds the volume with the right credentials.                                                   |
| Playwright source returns nothing            | Check `docker compose logs scraper` for `Browser closed` / `TimeoutError`. The per-host extractor in `scrapers/extractors/` may need a tweak for that ATS. |


For deeper topics see the focused docs:

- `docs/docker.md` — compose-specific notes, production deploys, switching to SQLite
- `docs/scheduler.md` — non-Docker scheduling (cron, launchd, EventBridge)
- `docs/auth.md` — bearer token setup, multiple tokens, frontend integration
- `docs/migrations.md` — adding/applying Alembic migrations

