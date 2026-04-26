"""Storage layer (SQLAlchemy Core, works on SQLite + Postgres)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import select, text, update
from sqlalchemy.engine import Engine

from .db import (
    companies_table,
    create_db_engine,
    job_embeddings_table,
    jobs_table,
    normalize_db_url,
    upsert_stmt,
)
from .models import Company, JobPosting


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, db: str | Path | None = None, *, engine: Engine | None = None) -> None:
        self.db_url = normalize_db_url(db) if engine is None else str(engine.url)
        self._engine: Engine = engine or create_db_engine(self.db_url)
        self._dialect = self._engine.dialect.name

    @property
    def dialect(self) -> str:
        return self._dialect

    def close(self) -> None:
        self._engine.dispose()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def upsert_companies(self, companies: Iterable[Company]) -> int:
        rows = [
            {
                "name": c.name,
                "careers_url": c.careers_url,
                "linkedin_url": c.linkedin_url,
                "country": c.country,
                "segment": c.segment,
            }
            for c in companies
        ]
        if not rows:
            return 0
        stmt = upsert_stmt(companies_table, ["name"], self._dialect)
        with self._engine.begin() as conn:
            conn.execute(stmt, rows)
        return len(rows)

    def upsert_jobs(self, jobs: Iterable[JobPosting]) -> tuple[int, int]:
        now = _now()
        inserted = refreshed = 0
        with self._engine.begin() as conn:
            for j in jobs:
                fp = j.fingerprint
                exists = conn.execute(
                    select(jobs_table.c.fingerprint).where(jobs_table.c.fingerprint == fp)
                ).first()
                if exists:
                    conn.execute(
                        update(jobs_table)
                        .where(jobs_table.c.fingerprint == fp)
                        .values(last_seen_at=now, status="open")
                    )
                    refreshed += 1
                else:
                    conn.execute(
                        jobs_table.insert().values(
                            fingerprint=fp,
                            company=j.company,
                            title=j.title,
                            url=j.url,
                            location=j.location,
                            department=j.department,
                            description=j.description,
                            source=j.source,
                            posted_at=j.posted_at,
                            scraped_at=j.scraped_at or now,
                            last_seen_at=now,
                            status="open",
                        )
                    )
                    inserted += 1
        return inserted, refreshed

    def mark_stale(self, before_iso: str) -> int:
        with self._engine.begin() as conn:
            res = conn.execute(
                update(jobs_table)
                .where(jobs_table.c.last_seen_at < before_iso)
                .where(jobs_table.c.status == "open")
                .values(status="closed")
            )
            return res.rowcount or 0

    def stats(self) -> dict:
        with self._engine.connect() as conn:
            n_companies = conn.execute(select(text("COUNT(*)")).select_from(companies_table)).scalar_one()
            n_jobs = conn.execute(select(text("COUNT(*)")).select_from(jobs_table)).scalar_one()
            n_open = conn.execute(
                select(text("COUNT(*)")).select_from(jobs_table).where(jobs_table.c.status == "open")
            ).scalar_one()
            rows = conn.execute(
                text("SELECT source, COUNT(*) AS c FROM jobs GROUP BY source ORDER BY c DESC")
            ).all()
        return {
            "companies": int(n_companies),
            "jobs": int(n_jobs),
            "open": int(n_open),
            "by_source": {r[0] or "": int(r[1]) for r in rows},
        }

    def get_embeddings(self, embedder: str) -> dict[str, bytes]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(job_embeddings_table.c.fingerprint, job_embeddings_table.c.vector).where(
                    job_embeddings_table.c.embedder == embedder
                )
            ).all()
        return {fp: bytes(blob) for fp, blob in rows}

    def upsert_embeddings(
        self, embedder: str, dim: int, items: Iterable[tuple[str, bytes]]
    ) -> int:
        now = _now()
        rows = [
            {"fingerprint": fp, "embedder": embedder, "dim": dim, "vector": vec, "created_at": now}
            for fp, vec in items
        ]
        if not rows:
            return 0
        stmt = upsert_stmt(job_embeddings_table, ["fingerprint", "embedder"], self._dialect)
        with self._engine.begin() as conn:
            conn.execute(stmt, rows)
        return len(rows)

    def open_jobs(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                jobs_table.select().where(jobs_table.c.status == "open")
                .order_by(jobs_table.c.last_seen_at.desc())
            ).mappings().all()
        return [dict(r) for r in rows]

    def all_jobs(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(jobs_table.select()).mappings().all()
        return [dict(r) for r in rows]

    def query_companies(
        self, *, segment: str | None = None, q: str | None = None, limit: int = 500
    ) -> list[dict]:
        sql = "SELECT * FROM companies"
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if segment:
            clauses.append("LOWER(segment) = LOWER(:segment)")
            params["segment"] = segment
        if q:
            clauses.append("LOWER(name) LIKE :q")
            params["q"] = f"%{q.lower()}%"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY name LIMIT :limit"
        params["limit"] = limit
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    def query_jobs(
        self,
        *,
        q: str | None = None,
        company: str | None = None,
        source: str | None = None,
        location: str | None = None,
        only_open: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> dict:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if only_open:
            clauses.append("status = 'open'")
        if q:
            clauses.append("(LOWER(title) LIKE :q OR LOWER(description) LIKE :q)")
            params["q"] = f"%{q.lower()}%"
        if company:
            clauses.append("LOWER(company) = LOWER(:company)")
            params["company"] = company
        if source:
            clauses.append("source LIKE :source")
            params["source"] = f"{source}%"
        if location:
            clauses.append("LOWER(location) LIKE :location")
            params["location"] = f"%{location.lower()}%"

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._engine.connect() as conn:
            total = conn.execute(text(f"SELECT COUNT(*) FROM jobs{where}"), params).scalar_one()
            rows = conn.execute(
                text(
                    f"SELECT * FROM jobs{where} ORDER BY last_seen_at DESC LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": limit, "offset": offset},
            ).mappings().all()
        return {"total": int(total), "items": [dict(r) for r in rows]}

    def export_jobs(self, out_path: str | Path, only_open: bool = True) -> int:
        sql = "SELECT * FROM jobs"
        if only_open:
            sql += " WHERE status='open'"
        with self._engine.connect() as conn:
            df = pd.read_sql_query(text(sql), conn)
        out = Path(out_path)
        if out.suffix.lower() == ".csv":
            df.to_csv(out, index=False)
        else:
            df.to_excel(out, index=False)
        return len(df)
