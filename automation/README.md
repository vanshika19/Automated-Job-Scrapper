# Weekly runs and “which step is running?” (without paid n8n Cloud)

## n8n is not only paid

- **[n8n self-hosted](https://docs.n8n.io/hosting/)** (Docker / your server) is **free** under the fair-code license. You pay for **n8n Cloud** and some enterprise features.
- The workflow in `n8n/workflows/weekly-job-scraper.json` is meant for a machine where **you** run n8n and shell commands.

## Option A — GitHub Actions (free tier, built-in step UI)

Use the workflow **`.github/workflows/weekly-scrape.yml`**.

- **Visualization:** GitHub → **Actions** → pick a run → each **step** (ATS, career, Playwright, LinkedIn jobs, LinkedIn posts) shows status, duration, and logs. No extra product.
- **Schedule:** Edit the `cron` in the file (default: Mondays 06:00 UTC).
- **Secrets:** In the repo, **Settings → Secrets and variables → Actions**, add at least `APIFY_TOKEN`. Add `DATABASE_URL` if you use a **hosted Postgres** (recommended); if you omit it, the job uses **SQLite on the runner** and the DB is **discarded** when the job finishes.

To run on demand: **Actions → Weekly job scrape → Run workflow**.

## Option B — macOS / Linux `cron` or `launchd` (free, no graph)

Minimal automation, no node canvas:

```cron
0 6 * * 1 cd /path/to/job-scrapper && /usr/bin/make scrape-sequential >> /var/log/job-scraper.log 2>&1
```

You only get log files; there is no built-in node diagram.

## Option C — Self-hosted orchestrators (free, heavier)

Tools like **Apache Airflow**, **Prefect**, or **Dagster** give a DAG UI and schedules, but need more setup than Actions or cron.

## Summary

| Approach | Cost | See “which step” |
|----------|------|-------------------|
| GitHub Actions | Free tier | Yes (step list + logs) |
| Self-hosted n8n | Free (your infra) | Yes (workflow canvas) |
| n8n Cloud | Paid tiers | Yes |
| cron / launchd | Free | No (logs only) |

For most repos, **GitHub Actions** is the simplest free substitute for n8n Cloud with clear per-step visibility.
