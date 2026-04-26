# Schema migrations (Alembic)

The schema is owned by Alembic. SQLAlchemy's `metadata.create_all()` is still
used for local SQLite convenience, but production paths (Docker compose,
Postgres) set `STORAGE_AUTO_CREATE=0` so Alembic is the single source of
truth.

## Layout

```
alembic.ini
migrations/
├── env.py                # resolves DATABASE_URL, registers metadata
├── script.py.mako        # template for new revisions
└── versions/
    └── 0001_initial.py   # baseline (companies, jobs, job_embeddings)
```

## Common commands

The repo wraps Alembic in the existing CLI so you don't need to remember the
`alembic` binary:

```bash
# Apply every pending migration.
python -m job_scraper migrate upgrade head

# Show what is currently applied.
python -m job_scraper migrate current

# Show the revision history.
python -m job_scraper migrate history

# Roll back one step.
python -m job_scraper migrate downgrade -1

# Generate a new auto-detected migration after editing job_scraper/db.py.
python -m job_scraper migrate revision --autogenerate -m "add foo column"
```

You can still call `alembic` directly if you prefer:

```bash
DATABASE_URL=postgresql+psycopg://jobs:jobs@localhost:5432/jobs alembic upgrade head
```

## Docker

Both the `api` and `scraper` containers run `python -m job_scraper migrate
upgrade head` before starting the actual workload, so a fresh
`docker compose up` always lands on the latest schema.

## Adding a column

1. Edit `job_scraper/db.py` so the `Table` reflects the new column.
2. Generate a migration:
   `python -m job_scraper migrate revision --autogenerate -m "add jobs.salary"`
3. Inspect / tidy the file under `migrations/versions/`.
4. Apply: `python -m job_scraper migrate upgrade head`.

For SQLite, `env.py` uses `render_as_batch=True` so additive column changes
work without manual table-rewrite gymnastics.
