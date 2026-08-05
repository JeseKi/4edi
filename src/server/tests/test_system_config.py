from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from src.server.auth.config import AuthConfig
from src.server.config import GlobalConfig, SystemConfig
from src.server.files.config import FilesConfig
from src.server.mail.config import MailConfig
from src.server.oauth.config import OAuthConfig
from src.server.platform.config import (
    AppConfig,
    DatabaseConfig,
    FrontendErrorReportingConfig,
    LoggingConfig,
    NotificationsConfig,
    TaskConfig,
    TaskDatabaseConfig,
)
from src.server.providers.config import ProvidersConfig
from src.server import settings_sources


def test_versioned_system_toml_supplies_non_sensitive_defaults() -> None:
    with (settings_sources.PROJECT_ROOT / "config" / "system.toml").open("rb") as config_file:
        toml_data = tomllib.load(config_file)

    global_settings = GlobalConfig()
    assert global_settings.app.port == toml_data["app"]["port"]
    assert global_settings.database.executor_max_workers == toml_data["database"]["executor_max_workers"]
    assert global_settings.files.allowed_extensions == toml_data["files"]["allowed_extensions"]
    assert global_settings.auth.access_token_ttl_minutes == toml_data["auth"]["access_token_ttl_minutes"]
    assert global_settings.mail.smtp_port == toml_data["mail"]["smtp_port"]
    assert global_settings.oauth.github_scope == toml_data["oauth"]["github_scope"]


def test_environment_variables_override_toml_and_keep_legacy_list_syntax(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://one.example, https://two.example")
    monkeypatch.setenv("OAUTH_LIST", "GITHUB")
    monkeypatch.setenv("MAIL_SMTP_PORT", "2525")

    global_settings = GlobalConfig()
    assert global_settings.app.port == 9001
    assert global_settings.app.allowed_origins == ["https://one.example", "https://two.example"]
    assert global_settings.oauth.enabled_providers == ["GITHUB"]
    assert global_settings.mail.smtp_port == 2525


def test_invalid_system_toml_fails_fast(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "system.toml"
    config_path.write_text("[app\nport = 8000\n", encoding="utf-8")
    monkeypatch.setattr(settings_sources, "SYSTEM_TOML_PATH", config_path)

    with pytest.raises(tomllib.TOMLDecodeError):
        GlobalConfig()


def test_all_system_configuration_fields_have_descriptive_metadata() -> None:
    configuration_models = (
        SystemConfig,
        AppConfig,
        DatabaseConfig,
        TaskDatabaseConfig,
        LoggingConfig,
        TaskConfig,
        FrontendErrorReportingConfig,
        NotificationsConfig,
        ProvidersConfig,
        FilesConfig,
        AuthConfig,
        MailConfig,
        OAuthConfig,
    )

    for model in configuration_models:
        for field_name, field in model.model_fields.items():
            assert field.title, f"{model.__name__}.{field_name} 缺少 title"
            assert field.description, f"{model.__name__}.{field_name} 缺少 description"


def test_every_active_system_toml_field_has_a_preceding_comment() -> None:
    lines = Path(settings_sources.SYSTEM_TOML_PATH).read_text(encoding="utf-8").splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "[")) or "=" not in stripped:
            continue
        previous = index - 1
        while previous >= 0 and not lines[previous].strip():
            previous -= 1
        assert previous >= 0 and lines[previous].lstrip().startswith("#"), (
            f"{stripped!r} 缺少前置配置说明注释"
        )
