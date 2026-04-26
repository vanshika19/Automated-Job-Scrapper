"""Bearer-token auth for the API.

Behaviour:
  - If `API_TOKEN` env var is unset/empty, the API is open (dev mode).
  - Otherwise every protected route requires `Authorization: Bearer <token>`
    matching one of the comma-separated tokens in `API_TOKEN`.
  - `/api/health` is intentionally always public so liveness checks work.
"""

from __future__ import annotations

import hmac
import os
from typing import Iterable

from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param


def _expected_tokens() -> list[str]:
    raw = os.environ.get("API_TOKEN", "").strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _matches(provided: str, expected: Iterable[str]) -> bool:
    for t in expected:
        if hmac.compare_digest(provided, t):
            return True
    return False


async def require_token(request: Request) -> None:
    expected = _expected_tokens()
    if not expected:
        return  # auth disabled

    auth_header = request.headers.get("authorization") or ""
    scheme, value = get_authorization_scheme_param(auth_header)
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header (expected `Bearer <token>`).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not _matches(value, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def is_enabled() -> bool:
    return bool(_expected_tokens())
