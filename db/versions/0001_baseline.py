"""Baseline schema for the application-owned `csip` schema.

Tables: sources (change-controlled registry), runs, job_events,
artifacts, raw_observations. Append-only discipline is enforced in the
DATABASE (triggers reject UPDATE/DELETE on job_events and
raw_observations), not merely in application code (SK-10).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "csip"

APPEND_ONLY_TABLES = ("job_events", "raw_observations")


def _create_append_only_trigger(table: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {SCHEMA}._reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'table % is append-only; UPDATE/DELETE rejected', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_{table}_append_only
        BEFORE UPDATE OR DELETE ON {SCHEMA}.{table}
        FOR EACH ROW EXECUTE FUNCTION {SCHEMA}._reject_mutation();
        """
    )


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(128), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("canonical_domain", sa.Text(), nullable=False),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("access_basis", sa.String(64), nullable=False),
        sa.Column("approved_methods", postgresql.JSONB(), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("approval_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("approval_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allowed_scope", postgresql.JSONB(), nullable=False),
        sa.Column("rate_limits", postgresql.JSONB(), nullable=False),
        sa.Column("retention", postgresql.JSONB(), nullable=False),
        sa.Column("stop_conditions", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False, unique=True),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("caller_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("page_family", sa.String(64), nullable=False),
        sa.Column("state", sa.String(48), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_runs_caller_idempotency", "runs",
        ["caller_id", "idempotency_key"], unique=True, schema=SCHEMA,
    )
    op.create_table(
        "job_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(64),
            sa.ForeignKey(f"{SCHEMA}.runs.run_id"), nullable=False,
        ),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("previous_state", sa.String(48), nullable=True),
        sa.Column("new_state", sa.String(48), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        schema=SCHEMA,
    )
    op.create_index("ix_job_events_run", "job_events", ["run_id"], schema=SCHEMA)
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.String(64), primary_key=True),
        sa.Column(
            "run_id", sa.String(64),
            sa.ForeignKey(f"{SCHEMA}.runs.run_id"), nullable=False,
        ),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("reference", sa.Text(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_fingerprint", sa.String(128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("storage_ref", sa.Text(), nullable=False),
        sa.Column("retrieval_metadata", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_artifacts_run_fingerprint", "artifacts",
        ["run_id", "content_fingerprint"], unique=True, schema=SCHEMA,
    )
    op.create_table(
        "raw_observations",
        sa.Column("observation_id", sa.String(64), primary_key=True),
        sa.Column(
            "run_id", sa.String(64),
            sa.ForeignKey(f"{SCHEMA}.runs.run_id"), nullable=False,
        ),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column(
            "artifact_id", sa.String(64),
            sa.ForeignKey(f"{SCHEMA}.artifacts.artifact_id"), nullable=False,
        ),
        sa.Column("field_key", sa.String(128), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_raw_obs_run_artifact_field", "raw_observations",
        ["run_id", "artifact_id", "field_key"], unique=True, schema=SCHEMA,
    )
    op.create_index(
        "ix_raw_obs_run", "raw_observations", ["run_id"], schema=SCHEMA,
    )

    for table in APPEND_ONLY_TABLES:
        _create_append_only_trigger(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {SCHEMA}.{table}")
    op.execute(f"DROP FUNCTION IF EXISTS {SCHEMA}._reject_mutation()")
    op.drop_index("ix_raw_obs_run", table_name="raw_observations", schema=SCHEMA)
    op.drop_index(
        "uq_raw_obs_run_artifact_field", table_name="raw_observations", schema=SCHEMA
    )
    op.drop_table("raw_observations", schema=SCHEMA)
    op.drop_index(
        "uq_artifacts_run_fingerprint", table_name="artifacts", schema=SCHEMA
    )
    op.drop_table("artifacts", schema=SCHEMA)
    op.drop_index("ix_job_events_run", table_name="job_events", schema=SCHEMA)
    op.drop_table("job_events", schema=SCHEMA)
    op.drop_index("uq_runs_caller_idempotency", table_name="runs", schema=SCHEMA)
    op.drop_table("runs", schema=SCHEMA)
    op.drop_table("sources", schema=SCHEMA)
