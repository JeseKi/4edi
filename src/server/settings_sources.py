"""Native TOML settings sources plus legacy flat-environment compatibility."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    TomlConfigSettingsSource,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_TOML_PATH = PROJECT_ROOT / "config" / "system.toml"

# Existing deployment variables predate the nested TOML document.  Keeping this
# translation in one source preserves those overrides without polluting the
# domain models with flat, environment-specific field names.
ENVIRONMENT_FIELDS: dict[str, dict[str, str]] = {
    "app": {
        "APP_ENV": "env",
        "ENABLED_FEATURES": "enabled_features",
        "ALLOWED_ORIGINS": "allowed_origins",
        "APP_SECRET_KEY": "secret_key",
        "APP_DOMAIN": "domain",
        "PORT": "port",
        "PROJECT_ROOT": "project_root",
    },
    "database": {
        "DATABASE_URL": "url",
        "DATABASE_POOL_SIZE": "pool_size",
        "DATABASE_MAX_OVERFLOW": "max_overflow",
        "DATABASE_POOL_TIMEOUT_SECONDS": "pool_timeout_seconds",
        "DATABASE_POOL_RECYCLE_SECONDS": "pool_recycle_seconds",
        "DATABASE_EXECUTOR_MAX_WORKERS": "executor_max_workers",
        "DATABASE_EXECUTOR_QUEUE_TIMEOUT_SECONDS": "executor_queue_timeout_seconds",
        "DATABASE_EXECUTOR_STATEMENT_TIMEOUT_SECONDS": "executor_statement_timeout_seconds",
        "DATABASE_MIGRATION_RETRY_ATTEMPTS": "migration_retry_attempts",
        "DATABASE_MIGRATION_RETRY_INTERVAL_SECONDS": "migration_retry_interval_seconds",
    },
    "task_database": {
        "TASK_DATABASE_POOL_SIZE": "pool_size",
        "TASK_DATABASE_MAX_OVERFLOW": "max_overflow",
        "TASK_DATABASE_POOL_TIMEOUT_SECONDS": "pool_timeout_seconds",
        "TASK_DATABASE_POOL_RECYCLE_SECONDS": "pool_recycle_seconds",
    },
    "logging": {
        "LOG_LEVEL": "level",
        "LOG_DIR": "directory",
        "LOG_ROTATION": "rotation",
        "LOG_RETENTION": "retention",
        "LOG_SERIALIZE": "serialize",
    },
    "tasks": {
        "TASK_IO_WORKERS": "io_workers",
        "TASK_NOTIFICATION_WORKERS": "notification_workers",
        "TASK_BATCH_WORKERS": "batch_workers",
        "TASK_SHUTDOWN_TIMEOUT_SECONDS": "shutdown_timeout_seconds",
        "TASK_DISPATCH_POLL_INTERVAL_SECONDS": "dispatch_poll_interval_seconds",
        "TASK_JOB_LEASE_SECONDS": "job_lease_seconds",
        "TASK_JOB_HEARTBEAT_INTERVAL_SECONDS": "job_heartbeat_interval_seconds",
    },
    "mail": {
        "MAIL_EXECUTOR_MAX_WORKERS": "executor_max_workers",
        "MAIL_EXECUTOR_QUEUE_TIMEOUT_SECONDS": "executor_queue_timeout_seconds",
        "MAIL_SMTP_HOST": "smtp_host",
        "MAIL_SMTP_PORT": "smtp_port",
        "MAIL_USE_SSL": "use_ssl",
        "MAIL_USE_TLS": "use_tls",
        "MAIL_TIMEOUT": "timeout",
        "MAIL_SENDER_EMAIL": "sender_email",
        "MAIL_SENDER_PASSWORD": "sender_password",
        "MAIL_SENDER_NAME": "sender_name",
    },
    "frontend_error_reporting": {
        "FRONTEND_ERROR_REPORTING_MAX_PAYLOAD_BYTES": "max_payload_bytes",
        "FRONTEND_ERROR_REPORTING_RATE_LIMIT_PER_MINUTE": "rate_limit_per_minute",
    },
    "notifications": {
        "NOTIFICATION_TRUSTED_EXTERNAL_ORIGINS": "trusted_external_origins",
    },
    "providers": {
        "EXTERNAL_PROVIDER_MOCK_LIST": "external_provider_mock_list",
        "EXAMPLE_EXTERNAL_API_BASE_URL": "example_external_api_base_url",
        "MOCK_PROVIDER_BACKEND_URL": "mock_provider_backend_url",
        "MOCK_PROVIDER_PUBLISH_INTERVAL_SECONDS": "mock_provider_publish_interval_seconds",
    },
    "files": {
        "FILE_STORAGE_DRIVER": "storage_driver",
        "FILE_LOCAL_ROOT": "local_root",
        "FILE_S3_BUCKET": "s3_bucket",
        "FILE_S3_REGION": "s3_region",
        "FILE_S3_ENDPOINT_URL": "s3_endpoint_url",
        "FILE_S3_ACCESS_KEY_ID": "s3_access_key_id",
        "FILE_S3_SECRET_ACCESS_KEY": "s3_secret_access_key",
        "FILE_S3_ADDRESSING_STYLE": "s3_addressing_style",
        "FILE_PRESIGN_TTL_SECONDS": "presign_ttl_seconds",
        "FILE_UPLOAD_TTL_MINUTES": "upload_ttl_minutes",
        "FILE_MAX_UPLOAD_BYTES": "max_upload_bytes",
        "FILE_ALLOWED_EXTENSIONS": "allowed_extensions",
    },
    "auth": {
        "JWT_SECRET_KEY": "jwt_secret_key",
        "JWT_ALGORITHM": "jwt_algorithm",
        "ACCESS_TOKEN_TTL_MINUTES": "access_token_ttl_minutes",
        "REFRESH_TOKEN_TTL_DAYS": "refresh_token_ttl_days",
        "REFRESH_COOKIE_NAME": "refresh_cookie_name",
        "REFRESH_COOKIE_SAMESITE": "refresh_cookie_samesite",
        "REFRESH_COOKIE_SECURE": "refresh_cookie_secure",
        "TEST_TOKEN": "test_token",
        "INIT_ADMIN_NAME": "init_admin_name",
        "INIT_ADMIN_PASSWORD": "init_admin_password",
        "INIT_ADMIN_EMAIL": "init_admin_email",
        "TWO_FACTOR_CHALLENGE_TTL_MINUTES": "two_factor_challenge_ttl_minutes",
        "TWO_FACTOR_SETUP_TTL_MINUTES": "two_factor_setup_ttl_minutes",
        "TWO_FACTOR_ISSUER_NAME": "two_factor_issuer_name",
        "TWO_FACTOR_ENCRYPTION_KEY": "two_factor_encryption_key",
        "TWO_FACTOR_BACKUP_CODE_COUNT": "two_factor_backup_code_count",
        "TWO_FACTOR_MAX_VERIFY_ATTEMPTS": "two_factor_max_verify_attempts",
        "TURNSTILE_ENABLED": "turnstile_enabled",
        "TURNSTILE_SECRET_KEY": "turnstile_secret_key",
        "TURNSTILE_VERIFY_TIMEOUT_SECONDS": "turnstile_verify_timeout_seconds",
    },
    "oauth": {
        "OAUTH_LIST": "enabled_providers",        "GITHUB_CLIENT_ID": "github_client_id",
        "GITHUB_CLIENT_SECRET": "github_client_secret",
        "GITHUB_REDIRECT_URI": "github_redirect_uri",
        "GITHUB_SCOPE": "github_scope",
        "GOOGLE_CLIENT_ID": "google_client_id",
        "GOOGLE_CLIENT_SECRET": "google_client_secret",
        "GOOGLE_REDIRECT_URI": "google_redirect_uri",
        "GOOGLE_SCOPE": "google_scope",
        "OAUTH_TICKET_TTL_MINUTES": "oauth_ticket_ttl_minutes",
        "OAUTH_STATE_TTL_MINUTES": "oauth_state_ttl_minutes",
    },
    "sms": {
        "TENCENTCLOUD_SECRET_ID": "secret_id",
        "TENCENTCLOUD_SECRET_KEY": "secret_key",
        "TENCENT_SMS_SDK_APP_ID": "sdk_app_id",
        "TENCENT_SMS_SIGN_NAME": "sign_name",
        "TENCENT_SMS_TEMPLATE_ID": "template_id",
        "TENCENT_SMS_REGION": "region",
        "TENCENT_SMS_ENDPOINT": "endpoint",
        "TENCENT_SMS_TIMEOUT_SECONDS": "timeout_seconds",
    },
    "mall": {
        "MALL_ORDER_PAY_TIMEOUT_MINUTES": "order_pay_timeout_minutes",
        "MALL_AUTO_CONFIRM_RECEIPT_DAYS": "auto_confirm_receipt_days",
        "MALL_DEFAULT_DEPOSIT_FEN": "default_deposit_fen",
        "MALL_FREIGHT_FEN": "freight_fen",
        "MALL_PAYMENT_MODE": "payment_mode",
        "WECHAT_PAY_APP_ID": "wechat_pay_app_id",
        "WECHAT_PAY_MERCHANT_ID": "wechat_pay_merchant_id",
        "WECHAT_PAY_PRIVATE_KEY_PATH": "wechat_pay_private_key_path",
        "WECHAT_PAY_CERT_SERIAL_NO": "wechat_pay_cert_serial_no",
        "WECHAT_PAY_APIV3_KEY": "wechat_pay_apiv3_key",
        "WECHAT_PAY_NOTIFY_BASE_URL": "wechat_pay_notify_base_url",
    },
}

LIST_ENVIRONMENT_FIELDS = {
    "ENABLED_FEATURES",
    "ALLOWED_ORIGINS",
    "EXTERNAL_PROVIDER_MOCK_LIST",
    "FILE_ALLOWED_EXTENSIONS",
    "NOTIFICATION_TRUSTED_EXTERNAL_ORIGINS",
    "OAUTH_LIST",
}


def _selected_app_env() -> str:
    if app_env := os.getenv("APP_ENV"):
        return app_env
    base_values = dotenv_values(PROJECT_ROOT / ".env")
    return str(base_values.get("APP_ENV") or "dev")


def _dotenv_values() -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for path in (PROJECT_ROOT / ".env", PROJECT_ROOT / f".env.{_selected_app_env()}"):
        if path.is_file():
            values.update(dotenv_values(path))
    return values


def _parse_legacy_list(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    if parsed is not None:
        return [str(parsed)]
    if "," in stripped:
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [stripped]


def _set_nested_value(target: dict[str, Any], section: str, field: str, value: Any) -> None:
    target.setdefault(section, {})[field] = value


class LegacyEnvironmentSettingsSource(PydanticBaseSettingsSource):
    """Translate existing flat environment variable names into nested settings."""

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        values: Mapping[str, str | None],
    ) -> None:
        super().__init__(settings_cls)
        self._values = {key.upper(): value for key, value in values.items()}

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        nested: dict[str, Any] = {}
        for section, fields in ENVIRONMENT_FIELDS.items():
            for environment_name, field_name in fields.items():
                raw_value = self._values.get(environment_name)
                if raw_value is None:
                    continue
                # MailConfig historically ignores empty MAIL_* values.
                if section == "mail" and raw_value == "":
                    continue
                value: str | list[str] = (
                    _parse_legacy_list(raw_value)
                    if environment_name in LIST_ENVIRONMENT_FIELDS
                    else raw_value
                )
                _set_nested_value(nested, section, field_name, value)
        return nested


class RequiredTomlConfigSettingsSource(TomlConfigSettingsSource):
    """Use Pydantic's TOML source while making the tracked file mandatory."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        if not SYSTEM_TOML_PATH.is_file():
            raise RuntimeError(f"缺少系统配置文件：{SYSTEM_TOML_PATH}")
        super().__init__(settings_cls, toml_file=SYSTEM_TOML_PATH)
