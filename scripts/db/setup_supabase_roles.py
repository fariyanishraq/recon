"""Bootstrap CSIP roles and schemas on a self-hosted Supabase/PostgreSQL.

Idempotent. Connects as the admin user (password from env), creates:

- schema ``csip``  : application-owned business tables (Phase 1 migrations)
- schema ``agno``  : Agno AgentOS runtime tables (owned by csip_agno)
- roles            : csip_migrate (DDL), csip_ingest (DML), csip_read (SELECT),
                     csip_agno (AgentOS runtime)

Generated role passwords are written into ``.env`` (gitignored) and are
NEVER printed to stdout. Run:

    python scripts/db/setup_supabase_roles.py --admin-password-env PGTEST_PW

Connection goes through the Supavisor pooler, so URLs in ``.env`` use the
``<role>.<tenant_id>`` username form.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

import pg8000.native

SCHEMA_APP = "csip"
SCHEMA_AGNO = "agno"
ROLES = ("csip_migrate", "csip_ingest", "csip_read", "csip_agno")

ENV_KEYS = {
    "csip_migrate": "CSIP_DB_MIGRATE_URL",
    "csip_ingest": "CSIP_DATABASE_URL",
    "csip_read": "CSIP_DB_READ_URL",
    "csip_agno": "CSIP_AGNO_DB_URL",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="postgres")
    parser.add_argument("--tenant-id", default="your-tenant-id",
                        help="Supavisor external_id (username suffix)")
    parser.add_argument("--admin-user", default="postgres",
                        help="Admin role connecting THROUGH the pooler "
                             "(e.g. postgres.your-tenant-id is handled by the pooler)")
    parser.add_argument("--admin-password-env", required=True,
                        help="Env var name holding the admin password (value never printed)")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--reset", action="store_true",
                        help="rotate passwords of existing roles")
    args = parser.parse_args()

    admin_password = os.environ.get(args.admin_password_env)
    if not admin_password:
        print(f"error: env var {args.admin_password_env} is not set", file=sys.stderr)
        return 2

    conn = pg8000.native.Connection(
        args.admin_user, host=args.host, port=args.port,
        password=admin_password, database=args.database, timeout=10,
    )

    created: dict[str, str] = {}

    def role_exists(role: str) -> bool:
        return bool(conn.run("SELECT 1 FROM pg_roles WHERE rolname = :r", r=role))

    def schema_exists(schema: str) -> bool:
        result = conn.run(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = :s",
            s=schema,
        )
        return bool(result)

    # Schemas (application-owned; Agno runtime tables live in their own schema)
    for schema in (SCHEMA_APP, SCHEMA_AGNO):
        if not schema_exists(schema):
            conn.run(f'CREATE SCHEMA "{schema}"')
            print(f"schema created: {schema}")
        else:
            print(f"schema exists:  {schema}")

    # Roles
    env_path = Path(args.env_file)
    existing_env = (
        env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    )
    stored_urls = {line.split("=", 1)[0]: line.split("=", 1)[1] for line in existing_env
                   if "=" in line and line.split("=", 1)[0] in ENV_KEYS.values()}

    for role in ROLES:
        has_url = ENV_KEYS[role] in stored_urls
        if not role_exists(role):
            password = secrets.token_urlsafe(24)
            # CREATE ROLE is a utility statement: bind parameters are not
            # supported, so the password is escaped and inlined.
            safe_password = password.replace("'", "''")
            conn.run(
                f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                f"PASSWORD '{safe_password}'"
            )
            created[role] = password
            print(f"role created:   {role}")
        elif args.reset or not has_url:
            # Existing role without a stored URL (or --reset): rotate its
            # password so .env stays authoritative.
            password = secrets.token_urlsafe(24)
            safe_password = password.replace("'", "''")
            conn.run(f'ALTER ROLE "{role}" PASSWORD \'{safe_password}\'')
            created[role] = password
            print(f"password reset: {role}")
        else:
            print(f"role exists:    {role} (password kept)")

    # Grant role membership to the admin role so it may SET ROLE for
    # ownership transfers and default-privilege management.
    for role in ROLES:
        conn.run(f'GRANT "{role}" TO "{args.admin_user.split(".")[0]}"')

    # Ownership/grants: agno schema is owned by csip_agno; app schema managed
    # by csip_migrate, written by csip_ingest, read by csip_read.
    conn.run(f'ALTER SCHEMA "{SCHEMA_AGNO}" OWNER TO "csip_agno"')
    conn.run(f'GRANT USAGE, CREATE ON SCHEMA "{SCHEMA_APP}" TO "csip_migrate"')
    conn.run(f'GRANT USAGE, CREATE ON SCHEMA "{SCHEMA_APP}" TO "csip_ingest"')
    conn.run(f'GRANT USAGE ON SCHEMA "{SCHEMA_APP}" TO "csip_read"')
    conn.run(f'GRANT ALL ON SCHEMA "{SCHEMA_AGNO}" TO "csip_agno"')
    conn.run(f'GRANT USAGE ON SCHEMA "{SCHEMA_AGNO}" TO "csip_migrate"')
    # Default privileges apply to objects created BY csip_migrate (the role
    # that runs Alembic), so scope them to that role.
    conn.run(f'ALTER DEFAULT PRIVILEGES FOR ROLE "csip_migrate" IN SCHEMA "{SCHEMA_APP}" GRANT '
             f'SELECT, INSERT, UPDATE, DELETE ON TABLES TO "csip_ingest"')
    conn.run(f'ALTER DEFAULT PRIVILEGES FOR ROLE "csip_migrate" IN SCHEMA "{SCHEMA_APP}" GRANT '
             f'SELECT ON TABLES TO "csip_read"')
    # Supavisor needs the roles usable through pooled connections
    for role in ROLES:
        conn.run(f'GRANT USAGE ON SCHEMA public TO "{role}"')

    # pg8000.native runs in autocommit; no explicit commit needed.
    conn.close()

    # Write generated/rotated credentials into .env (gitignored). Never print.
    if created:
        lines = existing_env
        for role, password in created.items():
            url = (f"postgresql+pg8000://{role}.{args.tenant_id}:{password}"
                   f"@{args.host}:{args.port}/{args.database}")
            lines = [ln for ln in lines if not ln.startswith(ENV_KEYS[role] + "=")]
            lines.append(f"{ENV_KEYS[role]}={url}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {len(created)} connection URL(s) into {args.env_file}")
    else:
        print("no new roles; .env unchanged (delete roles to regenerate)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
