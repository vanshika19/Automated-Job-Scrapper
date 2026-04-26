"""Resume <-> job AI matching via embeddings.

Backends:
  - SentenceTransformerEmbedder (default, local, free)
  - OpenAIEmbedder (auto-selected if OPENAI_API_KEY is set)

Embeddings for jobs are cached in the SQLite job_embeddings table keyed by
(fingerprint, embedder name) so re-runs only embed new postings.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence

import numpy as np

from .storage import Storage

LOG = logging.getLogger(__name__)


def _job_text(j: dict) -> str:
    parts = [
        j.get("title") or "",
        j.get("department") or "",
        j.get("location") or "",
        (j.get("description") or "")[:1500],
    ]
    return "\n".join(p for p in parts if p)


def _normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    name = "st:all-MiniLM-L6-v2"

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        LOG.info("Loading sentence-transformers model %s ...", model_name)
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        vecs = self._model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32)


class OpenAIEmbedder:
    name = "openai:text-embedding-3-small"
    dim = 1536

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        from openai import OpenAI

        self._client = OpenAI()
        self._model = model

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        out: list[list[float]] = []
        BATCH = 96
        for i in range(0, len(texts), BATCH):
            chunk = [t[:8000] for t in texts[i : i + BATCH]]
            resp = self._client.embeddings.create(model=self._model, input=chunk)
            out.extend([d.embedding for d in resp.data])
        return _normalize(np.asarray(out, dtype=np.float32))


def get_embedder(force: str | None = None) -> Embedder:
    pick = (force or os.environ.get("EMBEDDER", "")).lower()
    if pick == "openai" or (not pick and os.environ.get("OPENAI_API_KEY")):
        try:
            return OpenAIEmbedder()
        except Exception as e:  # noqa: BLE001
            LOG.warning("OpenAI embedder unavailable (%s); falling back to sentence-transformers", e)
    return SentenceTransformerEmbedder()


@dataclass
class MatchResult:
    score: float
    job: dict


def _bytes_to_vec(b: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32).reshape(-1, dim)[0]


def _vec_to_bytes(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def ensure_job_embeddings(
    db_url: str | Path,
    embedder: Embedder | None = None,
    *,
    only_open: bool = True,
) -> tuple[list[dict], np.ndarray, Embedder]:
    """Return (jobs, matrix, embedder). New jobs are embedded and cached."""
    emb = embedder or get_embedder()
    with Storage(db_url) as db:
        jobs = db.open_jobs() if only_open else db.all_jobs()
        cached = db.get_embeddings(emb.name)

        missing = [j for j in jobs if j["fingerprint"] not in cached]
        if missing:
            LOG.info("Embedding %d new jobs with %s ...", len(missing), emb.name)
            texts = [_job_text(j) for j in missing]
            vecs = emb.embed(texts)
            db.upsert_embeddings(
                emb.name,
                emb.dim,
                [(j["fingerprint"], _vec_to_bytes(v)) for j, v in zip(missing, vecs)],
            )
            for j, v in zip(missing, vecs):
                cached[j["fingerprint"]] = _vec_to_bytes(v)

        mat = np.vstack([_bytes_to_vec(cached[j["fingerprint"]], emb.dim) for j in jobs])
    return jobs, mat, emb


def match_resume(
    resume_text: str,
    db_url: str | Path,
    *,
    top_k: int = 25,
    embedder: Embedder | None = None,
    min_score: float = 0.0,
) -> list[MatchResult]:
    if not resume_text.strip():
        return []
    jobs, job_mat, emb = ensure_job_embeddings(db_url, embedder)
    if not jobs:
        return []
    rv = emb.embed([resume_text])[0]
    sims = (job_mat @ rv).astype(float)
    order = np.argsort(-sims)
    out: list[MatchResult] = []
    for i in order:
        s = float(sims[i])
        if s < min_score:
            break
        out.append(MatchResult(score=s, job=jobs[i]))
        if len(out) >= top_k:
            break
    return out
