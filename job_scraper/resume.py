"""Resume text extraction (PDF / TXT / MD)."""

from __future__ import annotations

import io
from pathlib import Path


def extract_text(path: str | Path) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(p.read_bytes())
    return p.read_text(encoding="utf-8", errors="ignore")


def extract_text_bytes(data: bytes, filename: str = "") -> str:
    if filename.lower().endswith(".pdf") or data[:5] == b"%PDF-":
        return _extract_pdf(data)
    return data.decode("utf-8", errors="ignore")


def _extract_pdf(data: bytes) -> str:
    try:
        import pdfplumber
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pdfplumber is required for PDF resumes (pip install pdfplumber)") from e
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for pg in pdf.pages:
            txt = pg.extract_text() or ""
            if txt:
                pages.append(txt)
    return "\n".join(pages).strip()
