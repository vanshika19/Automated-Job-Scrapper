# n8n layer (weekly runs + step visibility)

**Pricing:** [Self-hosted n8n](https://docs.n8n.io/hosting/) is free (fair-code); you typically pay for **[n8n Cloud](https://n8n.io/pricing/)** and enterprise add-ons. If you want a **free** hosted scheduler with a clear step-by-step UI, use **[GitHub Actions](../.github/workflows/weekly-scrape.yml)** — see [`automation/README.md`](../automation/README.md).

Use [n8n](https://n8n.io) as an orchestration UI on top of this repo: **Schedule Trigger** → chained **Execute Command** nodes (one per scraper). During a run, n8n highlights the **active node** and the **Executions** view shows each step’s logs and duration.

## Requirements

- **Self-hosted n8n** (Docker or npm) on a host that can run shell commands **on the same machine** as the clone (or mount the repo into the n8n container).  
  **n8n Cloud** does not run arbitrary shell on your laptop; use SSH + Execute Command, or run n8n where the repo lives.
- Repo prepared once: `make install`, `make playwright` (if you use Playwright), `.env` with `APIFY_TOKEN` and any LinkedIn settings.
- **Execute Command** is allowed in your n8n security settings (some installs disable it).

## One-time setup

1. Pick absolute path to the repo, e.g. `/Users/you/Applications/job-scrapper`.
2. In n8n: **Settings → Variables** (or your process env) add:

   | Name | Example value |
   |------|----------------|
   | `JOB_SCRAPER_ROOT` | `/Users/you/Applications/job-scrapper` |

3. Import workflow: **Workflows → Import from File** → `n8n/workflows/weekly-job-scraper.json`.
4. Open the workflow and **Execute Workflow** once manually to verify each node turns green in order.
5. **Activate** the workflow so the schedule runs.

## Schedule

The template uses cron **`0 8 * * 0`** (Sundays 08:00 **UTC**). Edit the **Schedule Trigger** node to your preferred day/time or timezone behavior.

## Why five nodes?

Each node runs one Makefile target (`make scrape-step-ats`, …). That matches one `--source` in the pipeline so the canvas shows **exactly** which scraper is running. A single `make scrape` would still work but appears as one step in n8n.

Local parity check:

```bash
cd "$JOB_SCRAPER_ROOT"
make scrape-sequential
```

## Optional: init DB before scrape

Add another **Execute Command** node **before** `1) ATS`:

```text
=cd {{ $env.JOB_SCRAPER_ROOT }} && export DATABASE_URL=sqlite:///jobs.db && make init
```

Run it weekly only if your workbooks change often, or trigger it manually / on a separate monthly schedule.

## Standalone LinkedIn posts list

If `.env` sets `LINKEDIN_POSTS_STANDALONE=1` (or URL list env vars), the CLI **rejects** mixing `linkedin_posts` with other sources. For that mode, use a **second workflow** with a single Execute Command: `make posts`, or remove nodes `4)` and `5)` from this chain and run posts separately.

## Import issues

n8n versions differ slightly. If import fails, create a blank workflow, add **Schedule Trigger** + five **Execute Command** nodes, and paste the command from `weekly-job-scraper.json` for each step.

## Security

Do not put `APIFY_TOKEN` in n8n nodes; keep it in repo `.env` (loaded by `python -m job_scraper`).
