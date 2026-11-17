"""Verify the live csip schema: triggers, ownership, role separation.

Run:  python scripts/db/verify_baseline.py
Requires CSIP_DB_MIGRATE_URL / CSIP_DATABASE_URL / CSIP_DB_READ_URL in .env.
Never prints credentials. Exit code 0 = all checks passed.
"""

from __future__ import annotations

from pathlib import Path

import pg8000.native as p


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
    return env


def connect(env: dict[str, str], key: str) -> p.Connection:
    url = env[key].split("://", 1)[1]
    userinfo, hostport = url.rsplit("@", 1)
    user, password = userinfo.split(":", 1)
    host, rest = hostport.split(":", 1)
    port, db = rest.split("/", 1)
    return p.Connection(
        user, host=host, port=int(port), password=password, database=db, timeout=10
    )


def main() -> int:
    env = load_env()
    failures: list[str] = []

    mig = connect(env, "CSIP_DB_MIGRATE_URL")
    tables = {
        row[0]
        for row in mig.run(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'csip'"
        )
    }
    expected_tables = {
        "artifacts", "csip_alembic_version", "job_events",
        "raw_observations", "runs", "sources",
    }
    missing = expected_tables - tables
    print(f"tables in csip schema: {sorted(tables)}")
    if missing:
        failures.append(f"missing tables: {missing}")

    triggers = mig.run(
        "SELECT event_object_table, trigger_name FROM information_schema.triggers "
        "WHERE trigger_schema = 'csip' ORDER BY 1, 2"
    )
    print(f"triggers: {triggers}")
    for table in ("job_events", "raw_observations"):
        names = {t[1] for t in triggers if t[0] == table}
        if f"trg_{table}_append_only" not in names:
            failures.append(f"append-only trigger missing on {table}")

    owners = mig.run(
        "SELECT tablename, tableowner FROM pg_tables WHERE schemaname = 'csip' ORDER BY 1"
    )
    print(f"owners: {owners}")
    for tablename, owner in owners:
        if tablename != "csip_alembic_version" and owner != "csip_migrate":
            failures.append(f"{tablename} owned by {owner}, expected csip_migrate")
    mig.close()

    ing = connect(env, "CSIP_DATABASE_URL")
    ing.run(
        "INSERT INTO csip.sources (source_id, name, canonical_domain, owner, "
        "access_basis, approved_methods, approval_status, enabled, allowed_scope, "
        "rate_limits, retention, stop_conditions) "
        "VALUES ('fixture-supplier-a', 'Supplier A Fixture', 'supplier-a.example', "
        "'internal', 'contract', '[\"http_get\"]'::jsonb, 'approved', true, "
        "'{\"path_prefixes\":[\"/catalog\"]}'::jsonb, '{\"max_rps\":1}'::jsonb, "
        "'{\"raw_days\":90}'::jsonb, '[]'::jsonb) ON CONFLICT (source_id) DO NOTHING"
    )
    ing.run(
        "INSERT INTO csip.runs (run_id, job_id, request_id, source_id, caller_id, "
        "idempotency_key, page_family, state) "
        "VALUES ('run_verify_1', 'job_verify_1', 'req_verify_1', "
        "'fixture-supplier-a', 'verify-caller', 'verify-idem-1', "
        "'product_detail', 'PENDING') ON CONFLICT DO NOTHING"
    )
    ing.run(
        "INSERT INTO csip.artifacts (artifact_id, run_id, source_id, artifact_type, "
        "reference, captured_at, content_fingerprint, byte_size, storage_ref, "
        "retrieval_metadata) VALUES ('art_verify_1', 'run_verify_1', "
        "'fixture-supplier-a', 'page_html', 'fixture://supplier-a/p/1', now(), "
        "'fp_verify_1', 100, 'fixture://store/1', '{}'::jsonb) "
        "ON CONFLICT DO NOTHING"
    )
    ing.run(
        "INSERT INTO csip.raw_observations (observation_id, run_id, source_id, "
        "artifact_id, field_key, raw_value, language, captured_at, evidence, "
        "parser_version, schema_version) VALUES ('obs_verify_1', 'run_verify_1', "
        "'fixture-supplier-a', 'art_verify_1', 'title', 'Widget A', 'en', now(), "
        "'{}'::jsonb, 'fixture-parser-1', '1') ON CONFLICT DO NOTHING"
    )
    print("ingest role: INSERT into all five tables OK")

    ing.run(
        "INSERT INTO csip.job_events (run_id, stage, previous_state, new_state, "
        "actor, payload) VALUES ('run_verify_1', 'submission', NULL, 'PENDING', "
        "'verify', '{}'::jsonb)"
    )

    for stmt, label in (
        ("UPDATE csip.job_events SET new_state = 'TAMPERED'", "job_events UPDATE"),
        ("DELETE FROM csip.job_events", "job_events DELETE"),
        ("UPDATE csip.raw_observations SET raw_value = 'TAMPERED'", "raw_obs UPDATE"),
        ("DELETE FROM csip.raw_observations", "raw_obs DELETE"),
    ):
        try:
            ing.run(stmt)
            failures.append(f"{label} was ALLOWED (append-only broken)")
        except Exception as exc:
            first = str(exc).splitlines()[0][:90]
            print(f"append-only {label} rejected: {first}")
    ing.close()

    rd = connect(env, "CSIP_DB_READ_URL")
    count = rd.run("SELECT count(*) FROM csip.sources")[0][0]
    print(f"read role SELECT OK (sources count: {count})")
    try:
        rd.run(
            "INSERT INTO csip.sources (source_id, name) VALUES ('nope', 'nope')"
        )
        failures.append("read role could INSERT (privilege escalation)")
    except Exception as exc:
        print(f"read-role INSERT correctly denied: {str(exc).splitlines()[0][:70]}")
    rd.close()

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nALL BASELINE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
