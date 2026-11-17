"""Typed, fail-fast configuration.

Configuration is validated at startup; invalid or unsafe configuration
refuses to boot (agent.md Step 4: strict validation at trust boundaries).
Secrets are never defaulted to real values and never logged.
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from csip.shared.errors import ConfigurationError

# Hosts on which a CDP debugging endpoint may be bound. The debugging
# endpoint is a privileged interface and must never be publicly reachable
# (blueprint 3.4, goals G8). Note: 0.0.0.0 is the wildcard bind (all
# interfaces) and is therefore NOT acceptable.
_PRIVATE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", ""})


class Settings(BaseSettings):
    """Environment-driven settings (prefix ``CSIP_``)."""

    model_config = SettingsConfigDict(
        env_prefix="CSIP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    local_mode: bool = True
    app_env: Literal["local", "dev", "staging", "production"] = "local"
    log_level: str = "INFO"

    database_url: str | None = None
    db_ingest_role: str = "csip_ingest"

    agno_db_url: str | None = None
    agno_queue_max_concurrency: int = Field(default=2, ge=1, le=16)
    agno_queue_max_depth: int = Field(default=100, ge=1)
    agno_queue_max_attempts: int = Field(default=1, ge=1, le=3)

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    cdp_enabled: bool = False
    cdp_bind_host: str = "127.0.0.1"
    cdp_port: int = Field(default=9222, ge=1, le=65535)
    browser_profile_dir: str = "artifacts/local-only/browser-profile"

    max_pages_per_run: int = Field(default=10, ge=1, le=1000)
    max_concurrency: int = Field(default=1, ge=1, le=8)
    http_timeout_seconds: int = Field(default=30, ge=1, le=300)

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"unsupported log level: {value!r}")
        return upper

    @model_validator(mode="after")
    def _validate_safety(self) -> Settings:
        # Rule 1: non-local mode requires a database URL (system of record).
        if not self.local_mode and not self.database_url:
            raise ValueError("CSIP_DATABASE_URL is required when CSIP_LOCAL_MODE=false")

        # Rule 2: whole-job retries stay disabled until idempotency is proven.
        if self.agno_queue_max_attempts > 1:
            raise ValueError(
                "CSIP_AGNO_QUEUE_MAX_ATTEMPTS > 1 is forbidden until external "
                "side effects are proven idempotent (blueprint 8.2)"
            )

        # Rule 3: CDP endpoint must bind to loopback or a private address.
        if self.cdp_enabled and not _is_private_bind_host(self.cdp_bind_host):
            raise ValueError(
                "CSIP_CDP_BIND_HOST must be loopback or a private-network address; "
                "the debugging endpoint must never be publicly reachable"
            )
        return self

    @property
    def safe_summary(self) -> dict[str, str | int | bool]:
        """Loggable summary with zero secrets."""
        return {
            "local_mode": self.local_mode,
            "app_env": self.app_env,
            "log_level": self.log_level,
            "database_configured": bool(self.database_url),
            "agno_db_configured": bool(self.agno_db_url),
            "queue_max_attempts": self.agno_queue_max_attempts,
            "cdp_enabled": self.cdp_enabled,
            "cdp_bind_host": self.cdp_bind_host,
            "max_pages_per_run": self.max_pages_per_run,
        }


def _is_private_bind_host(host: str) -> bool:
    if host in _PRIVATE_HOSTS:
        return True
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    if addr.version == 4 and int(addr) < 256**3:  # 0.0.0.0/8 ("this network")
        # Addresses in 0.0.0.0/8 are not valid private bind targets.
        return False
    return addr.is_private or addr.is_loopback


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Load and validate settings once per process; raises on unsafe config."""
    try:
        return Settings()
    except ValueError as exc:
        raise ConfigurationError(f"invalid configuration: {exc}") from None
