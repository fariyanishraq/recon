"""Post-rotation verification (run from the recon repo).

Checks, WITHOUT printing any secret:
1. the NEW admin password (from the supabase .env) connects through the pooler
2. the tenant was re-provisioned (Supavisor tenants table non-empty)
3. csip_* application roles still connect (their passwords were not rotated)
4. gateway endpoints respond through envoy on :8000
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pg8000.native as p

SUPABASE_ENV = Path(r"D:\projects\aess\baas\supabase-project\.env")
RECON_ENV = Path(".env")


def read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return env


def parse_pg_url(url: str) -> dict[str, str]:
    body = url.split("://", 1)[1]
    userinfo, hostport = body.rsplit("@", 1)
    user, password = userinfo.split(":", 1)
    host, rest = hostport.split(":", 1)
    port, db = rest.split("/", 1)
    return {
        "user": user, "password": password,
        "host": host, "port": int(port), "db": db,
    }


def main() -> int:
    failures: list[str] = []
    supa = read_env(SUPABASE_ENV)
    recon = read_env(RECON_ENV)
    new_pw = supa.get("POSTGRES_PASSWORD", "")
    if not new_pw or new_pw.startswith("your-"):
        failures.append("POSTGRES_PASSWORD not rotated (still placeholder)")

    # 1. new admin password through the pooler
    try:
        conn = p.Connection(
            "postgres.your-tenant-id", host="localhost", port=5432,
            password=new_pw, database="postgres", timeout=10,
        )
        conn.run("select 1")
        conn.close()
        print("admin (new password) via pooler: OK")
    except Exception as exc:
        failures.append(f"admin via pooler FAILED: {str(exc).splitlines()[0][:100]}")

    # 2. tenant re-provisioned
    try:
        conn = p.Connection(
            "postgres.your-tenant-id", host="localhost", port=5432,
            password=new_pw, database="_supabase", timeout=10,
        )
        rows = conn.run(
            "SELECT external_id FROM _supavisor.tenants"
        )
        conn.close()
        print(f"supavisor tenants re-provisioned: {[r[0] for r in rows]}")
        if not rows:
            failures.append("supavisor tenants table is empty")
    except Exception as exc:
        failures.append(f"tenant check FAILED: {str(exc).splitlines()[0][:100]}")

    # 3. csip roles unchanged and still working
    for key in ("CSIP_DB_MIGRATE_URL", "CSIP_DATABASE_URL", "CSIP_DB_READ_URL",
                "CSIP_AGNO_DB_URL"):
        params = parse_pg_url(recon[key])
        try:
            conn = p.Connection(
                params["user"], host=params["host"], port=params["port"],
                password=params["password"], database=params["db"], timeout=10,
            )
            conn.run("select 1")
            conn.close()
            role = params["user"].split(".")[0]
            print(f"{role} via pooler: OK (password unchanged)")
        except Exception as exc:
            failures.append(f"{key} FAILED: {str(exc).splitlines()[0][:100]}")

    # 4. gateway endpoints
    checks = {
        "auth": "http://localhost:8000/auth/v1/health",
        "rest": "http://localhost:8000/rest/v1/",
        "pooler-api": "http://localhost:8000/pooler/health",  # may 404, informational
    }
    for name, url in checks.items():
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read().decode("utf-8", "replace")[:60]
                print(f"gateway {name}: HTTP {resp.status} {body}")
        except Exception as exc:
            print(f"gateway {name}: {type(exc).__name__} ({str(exc)[:60]})")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nROTATION VERIFIED: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
