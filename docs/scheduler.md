# Scheduling the scraper

The pipeline is a plain CLI invocation, so any scheduler works. The recommended
deployment is the Docker Compose stack (`docs/docker.md`) — it ships with a
`scraper` container that runs supercronic on the schedule defined in
`docker/crontab`. The recipes below are alternatives for non-container hosts.

## Local cron (macOS / Linux)

```bash
crontab -e
```

```cron
PATH=/usr/local/bin:/usr/bin:/bin
PROJECT=/Users/vanshikasingh/Applications/job-scrapper

0 */6 * * *  cd $PROJECT && .venv/bin/python -m job_scraper scrape --source ats career --sleep 0.6 >> $PROJECT/logs/scrape.log 2>&1
30 */6 * * * cd $PROJECT && .venv/bin/python -m job_scraper export $PROJECT/jobs_open.xlsx >> $PROJECT/logs/export.log 2>&1
```

## launchd (macOS, native)

Save as `~/Library/LaunchAgents/com.jobscrapper.scrape.plist` and `launchctl
load` it. Use `StartInterval` (seconds) or `StartCalendarInterval`.

## AWS EventBridge -> Fargate

1. `docker build -f Dockerfile.scraper -t <repo>/job-scraper:latest .`
2. Push to ECR.
3. Define an ECS task that runs `python -m job_scraper scrape --source ats career`
   with `DATABASE_URL` set to your RDS instance.
4. Create an EventBridge schedule (e.g. `rate(6 hours)`) that triggers the
   task. The image already has Chromium, so you can run Playwright sources too.

## Render / Railway / Fly.io cron

These platforms accept cron expressions in their UI and run the same
`python -m job_scraper scrape` command in a worker dyno. Set `DATABASE_URL`
to their managed Postgres connection string.

## Closing stale postings

Every successful run refreshes `last_seen_at` for postings still on the source.
To close ghost listings, pass an ISO cutoff:

```python
from job_scraper.pipeline import run
run(companies, "postgresql+psycopg://...", mark_stale_older_than="2026-04-01T00:00:00+00:00")
```

The job stays in the DB with `status='closed'` so historical reporting works;
the dashboard hides them by default.
