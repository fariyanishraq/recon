"""Alembic environment.

Reads the database URL from CSIP_DATABASE_URL so credentials never live in
this file. Until Phase 1 lands the initial schema, metadata is empty and
migrations fail closed with a clear error rather than touching a database.
"""

from __future__ import annotations

import os
import re

from alembic import context
from sqlalchemy import create_engine

config = context.config


def _database_url() -> str:
    # Migrations run under the dedicated least-privilege DDL role
    # (csip_migrate). The app-writer URL is only a fallback for dev.
    url = os.environ.get("CSIP_DB_MIGRATE_URL", "") or os.environ.get(
        "CSIP_DATABASE_URL", ""
    )
    if not url:
        raise RuntimeError(
            "CSIP_DB_MIGRATE_URL (or CSIP_DATABASE_URL) is not set; refusing "
            "to run migrations (fail-closed migration discipline)"
        )
    return url


def _redact(url: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@]+@", r"\1***@", url)


def _version_table_kwargs() -> dict:
    # Keep Alembic's bookkeeping inside the application-owned schema so the
    # csip_migrate role (which only has CREATE on `csip`) can manage it.
    return {"version_table": "csip_alembic_version", "version_table_schema": "csip"}


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=None,  # application-owned metadata lives in migrations
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_version_table_kwargs(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,  # application-owned metadata lives in migrations
            **_version_table_kwargs(),
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

assert _redact  # imported for reuse; never log raw URLs
