"""FastAPI app exposing jobs, companies, stats, and resume matching.

Run with:  uvicorn job_scraper.api:app --reload --port 8000

Database is selected via:
  - DATABASE_URL  (sqlite:///path/jobs.db, postgresql+psycopg://...)
  - JOB_SCRAPER_DB (legacy: filesystem path)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import auth, resume as resume_mod
from .db import normalize_db_url
from .matching import match_resume
from .storage import Storage

LOG = logging.getLogger("job_scraper.api")


def _resolve_db_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    legacy = os.environ.get("JOB_SCRAPER_DB")
    if legacy:
        return normalize_db_url(legacy)
    return normalize_db_url(Path(__file__).resolve().parent.parent / "jobs.db")


DB_URL = _resolve_db_url()

app = FastAPI(title="Job Scraper API", version="0.2.0")

allowed = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _db() -> Storage:
    return Storage(DB_URL)


@app.get("/api/health")
def health() -> dict:
    try:
        with _db() as db:
            db.stats()
        return {"ok": True, "auth_required": auth.is_enabled()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "auth_required": auth.is_enabled(), "error": str(e)}


@app.get("/api/stats", dependencies=[Depends(auth.require_token)])
def stats() -> dict:
    with _db() as db:
        return db.stats()


@app.get("/api/companies", dependencies=[Depends(auth.require_token)])
def companies(
    segment: str | None = None,
    q: str | None = None,
    limit: int = Query(500, le=2000),
) -> list[dict]:
    with _db() as db:
        return db.query_companies(segment=segment, q=q, limit=limit)


@app.get("/api/jobs", dependencies=[Depends(auth.require_token)])
def jobs(
    q: str | None = None,
    company: str | None = None,
    source: str | None = None,
    location: str | None = None,
    only_open: bool = True,
    limit: int = Query(200, le=2000),
    offset: int = 0,
) -> dict:
    with _db() as db:
        return db.query_jobs(
            q=q,
            company=company,
            source=source,
            location=location,
            only_open=only_open,
            limit=limit,
            offset=offset,
        )


@app.post("/api/match", dependencies=[Depends(auth.require_token)])
async def match(
    resume: UploadFile = File(...),
    top_k: int = Form(25),
    min_score: float = Form(0.0),
) -> dict:
    try:
        data = await resume.read()
        text = resume_mod.extract_text_bytes(data, resume.filename or "")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not read resume: {e}") from e
    if not text.strip():
        raise HTTPException(400, "Empty resume text")

    results = match_resume(text, DB_URL, top_k=top_k, min_score=min_score)
    return {
        "resume_chars": len(text),
        "results": [{"score": round(r.score, 4), **r.job} for r in results],
    }
