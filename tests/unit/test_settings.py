"""Tests: configuration validation fail-fast rules (security baseline)."""

from __future__ import annotations

import pytest

from csip.infrastructure.config.settings import Settings, _is_private_bind_host
from csip.shared.errors import ConfigurationError


def settings(**kwargs) -> Settings:
    base = dict(
        _env_file=None,  # never read a real .env during tests
        local_mode=True,
        app_env="local",
    )
    return Settings(**{**base, **kwargs})


class TestDatabaseRequirement:
    def test_non_local_mode_requires_database_url(self) -> None:
        with pytest.raises(ValueError, match="CSIP_DATABASE_URL"):
            settings(local_mode=False, database_url=None)

    def test_non_local_mode_with_database_url_ok(self) -> None:
        s = settings(local_mode=False, database_url="postgresql://u:p@localhost/db")
        assert s.local_mode is False


class TestQueueRetries:
    def test_multiple_queue_attempts_forbidden(self) -> None:
        with pytest.raises(ValueError, match="idempotent"):
            settings(agno_queue_max_attempts=2)

    def test_single_attempt_default_ok(self) -> None:
        assert settings().agno_queue_max_attempts == 1


class TestCDPExposure:
    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "10.0.0.5", "192.168.1.2"])
    def test_private_bind_hosts_allowed(self, host: str) -> None:
        assert _is_private_bind_host(host) is True

    @pytest.mark.parametrize("host", ["0.35.12.9", "8.8.8.8", "example.com", "1.2.3.4"])
    def test_public_bind_hosts_rejected(self, host: str) -> None:
        assert _is_private_bind_host(host) is False

    def test_cdp_public_binding_fails_startup(self) -> None:
        with pytest.raises(ValueError, match="CDP_BIND_HOST"):
            settings(cdp_enabled=True, cdp_bind_host="0.0.0.0")

    def test_cdp_public_host_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="CDP_BIND_HOST"):
            settings(cdp_enabled=True, cdp_bind_host="csip.example.com")

    def test_cdp_disabled_allows_any_setting(self) -> None:
        s = settings(cdp_enabled=False, cdp_bind_host="8.8.8.8")
        assert s.cdp_enabled is False


class TestLogLevels:
    def test_invalid_log_level_rejected(self) -> None:
        with pytest.raises(ValueError, match="log level"):
            settings(log_level="VERBOSE")


class TestLoadSettings:
    def test_invalid_env_raises_configuration_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CSIP_LOCAL_MODE", "false")
        monkeypatch.setenv("CSIP_DATABASE_URL", "")
        from csip.infrastructure.config.settings import load_settings

        load_settings.cache_clear()
        with pytest.raises(ConfigurationError):
            load_settings()
        load_settings.cache_clear()
