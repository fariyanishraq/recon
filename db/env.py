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


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=None,  # Phase 1: application-owned metadata
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="csip_alembic_version",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,  # Phase 1: application-owned metadata
            version_table="csip_alembic_version",
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

assert _redact  # imported for reuse; never log raw URLs
