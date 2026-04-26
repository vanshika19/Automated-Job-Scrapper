"""SQLAlchemy engine + schema (works on SQLite and Postgres).

`db_url` accepts either:
  - a SQLAlchemy URL (`sqlite:///jobs.db`, `postgresql+psycopg://user:pw@host/db`)
  - a filesystem path (treated as `sqlite:///<path>`)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


metadata = MetaData()

companies_table = Table(
    "companies",
    metadata,
    Column("name", String, primary_key=True),
    Column("careers_url", Text, default=""),
    Column("linkedin_url", Text, default=""),
    Column("country", Text, default=""),
    Column("segment", Text, default=""),
)

jobs_table = Table(
    "jobs",
    metadata,
    Column("fingerprint", String(64), primary_key=True),
    Column("company", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("url", Text),
    Column("location", Text),
    Column("department", Text),
    Column("description", Text),
    Column("source", Text),
    Column("posted_at", Text),
    Column("scraped_at", Text),
    Column("last_seen_at", Text),
    Column("status", Text, default="open"),
    Index("idx_jobs_company", "company"),
    Index("idx_jobs_source", "source"),
    Index("idx_jobs_status", "status"),
)

job_embeddings_table = Table(
    "job_embeddings",
    metadata,
    Column("fingerprint", String(64), primary_key=True),
    Column("embedder", String(128), primary_key=True),
    Column("dim", Integer, nullable=False),
    Column("vector", LargeBinary, nullable=False),
    Column("created_at", Text, nullable=False),
)


def normalize_db_url(db: str | Path | None) -> str:
    if db is None:
        return "sqlite:///jobs.db"
    s = str(db)
    if "://" in s:
        return s
    return f"sqlite:///{Path(s).as_posix()}"


def create_db_engine(db_url: str, *, auto_create: bool | None = None) -> Engine:
    """Build a SQLAlchemy engine.

    `auto_create` defaults to the value of `STORAGE_AUTO_CREATE` (true) so
    sqlite dev workflows continue to work without Alembic. Set
    `STORAGE_AUTO_CREATE=0` (or pass `auto_create=False`) when Alembic owns
    the schema, e.g. inside docker-compose.
    """
    kwargs: dict[str, Any] = {"future": True}
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    eng = create_engine(db_url, **kwargs)
    if auto_create is None:
        auto_create = os.environ.get("STORAGE_AUTO_CREATE", "1") not in ("0", "false", "False")
    if auto_create:
        metadata.create_all(eng)
    return eng


def upsert_stmt(table: Table, keys: Iterable[str], dialect: str):
    """Return a dialect-appropriate INSERT ... ON CONFLICT DO UPDATE statement.

    Caller must `.values(rows)` and execute. `keys` are the conflict keys;
    every other column gets refreshed from `excluded`.
    """
    key_list = list(keys)
    if dialect == "postgresql":
        ins = pg_insert(table)
        update_cols = {c.name: ins.excluded[c.name] for c in table.columns if c.name not in key_list}
        return ins.on_conflict_do_update(index_elements=key_list, set_=update_cols)
    ins = sqlite_insert(table)
    update_cols = {c.name: ins.excluded[c.name] for c in table.columns if c.name not in key_list}
    return ins.on_conflict_do_update(index_elements=key_list, set_=update_cols)
