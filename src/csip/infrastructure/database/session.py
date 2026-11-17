"""Engine/session factory for the application database.

The database URL always comes from settings/environment - never hardcoded.
On this machine the psycopg compiled DLL is blocked by policy, so the
project standardizes on the pure-Python pg8000 driver
(``postgresql+pg8000://`` URLs, enforced by ``scripts/db/setup_supabase_roles.py``).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def require_pg8000_url(url: str) -> str:
    """Force the pure-Python driver; refuse to fall back to blocked DLLs."""
    if not url.startswith("postgresql+pg8000://"):
        raise ValueError(
            "CSIP database URLs must use the pg8000 driver "
            "(postgresql+pg8000://); the psycopg compiled DLL is blocked by "
            "machine policy"
        )
    return url


def build_engine(url: str, *, pool_pre_ping: bool = True, **kwargs: Any) -> Engine:
    return create_engine(
        require_pg8000_url(url),
        pool_pre_ping=pool_pre_ping,
        future=True,
        **kwargs,
    )
