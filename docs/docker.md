# Running with Docker Compose

The compose file spins up four services:

| service    | image                                          | role                                       |
|------------|------------------------------------------------|--------------------------------------------|
| `db`       | `postgres:16-alpine`                           | persistent storage                         |
| `api`      | built from `Dockerfile`                        | FastAPI on `:8000` (and `init-db` on boot) |
| `scraper`  | built from `Dockerfile.scraper` (Playwright)   | supercronic running ATS / career / Playwright scrapes |
| `frontend` | built from `frontend/Dockerfile` (nginx + Vite build) | dashboard on `:8080`, proxies `/api` -> `api` |

## First run

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

- API:        http://localhost:8000/api/health
- Dashboard:  http://localhost:8080

The `api` container runs `python -m job_scraper init-db` on every start, which
loads the four `*_structured.xlsx` registries into Postgres. After that the
`scraper` container immediately runs supercronic with the schedule in
`docker/crontab` (every 6h ATS, twice/day career, daily Playwright + Excel
export).

## Triggering a scrape on demand

```bash
# One-off ATS scrape against the running Postgres.
docker compose run --rm scraper python -m job_scraper scrape --source ats --segment Fintech

# Render a JS-heavy career page with Playwright.
docker compose run --rm scraper python -m job_scraper scrape --source playwright --only "Stripe"

# Export the open jobs to xlsx (lands in the `exports` named volume).
docker compose run --rm scraper python -m job_scraper export /app/data/jobs_open.xlsx
```

## Switching to SQLite (single-host)

If you don't want Postgres, point the api + scraper at a sqlite file in a
shared volume by editing `.env`:

```env
DATABASE_URL=sqlite:////app/data/jobs.db
```

and add a shared volume mount under both services:

```yaml
volumes:
  - exports:/app/data
```

Postgres is the recommended default once you start scaling past a single host.

## Logs

```bash
docker compose logs -f api
docker compose logs -f scraper
```

Each cron tick prints `[<timestamp>] scrape source=<src>` followed by the
pipeline's summary JSON.

## Production notes

- Replace the default Postgres password in `.env` and consider rotating into
  a managed Postgres (RDS, Cloud SQL, Neon).
- The `hf_cache` volume keeps the sentence-transformers model warm across
  container restarts (~80MB). For OpenAI embeddings, set `OPENAI_API_KEY` and
  the matcher swaps automatically.
- Behind a reverse proxy (Cloudflare, ALB, etc.) terminate TLS in front of
  the `frontend` container; nginx already handles SPA routing and `/api`
  proxying.
