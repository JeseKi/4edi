# -*- coding: utf-8 -*-
"""Compose the domain-owned sections into the application's system settings."""

from __future__ import annotations

import os
from typing import Any

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from src.server.auth.config import AuthConfig
from src.server.compliance.config import ComplianceConfig
from src.server.auth.sms_config import SmsConfig
from src.server.files.config import FilesConfig
from src.server.mail.config import MailConfig
from src.server.mall.config import MallConfig
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
from src.server.settings_sources import (
    ENVIRONMENT_FIELDS,
    LegacyEnvironmentSettingsSource,
    RequiredTomlConfigSettingsSource,
    _dotenv_values,
)


class SystemConfig(BaseSettings):
    """One nested model whose structure directly matches ``config/system.toml``."""

    app: AppConfig = Field(
        default_factory=AppConfig,
        title="应用配置",
        description="环境、功能包、域名和 HTTP 服务配置。",
    )
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        title="Web 数据库配置",
        description="Web 进程数据库连接、连接池和短事务执行器配置。",
    )
    task_database: TaskDatabaseConfig = Field(
        default_factory=TaskDatabaseConfig,
        title="Worker 数据库配置",
        description="后台 worker 使用的独立数据库连接池配置。",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        title="日志配置",
        description="控制台和文件日志输出配置。",
    )
    tasks: TaskConfig = Field(
        default_factory=TaskConfig,
        title="后台任务配置",
        description="持久化后台任务队列和 worker 配置。",
    )
    mail: MailConfig = Field(
        default_factory=MailConfig,
        title="邮件配置",
        description="SMTP 邮件发送及其受控执行器配置。",
    )
    frontend_error_reporting: FrontendErrorReportingConfig = Field(
        default_factory=FrontendErrorReportingConfig,
        title="前端错误上报配置",
        description="前端错误收集接口的请求体和限流配置。",
    )
    notifications: NotificationsConfig = Field(
        default_factory=NotificationsConfig,
        title="通知配置",
        description="通知功能的受信任外部来源配置。",
    )
    providers: ProvidersConfig = Field(
        default_factory=ProvidersConfig,
        title="外部 Provider 配置",
        description="外部服务 real/mock 选择及目标地址配置。",
    )
    files: FilesConfig = Field(
        default_factory=FilesConfig,
        title="文件资产配置",
        description="上传文件的存储、大小与类型限制配置。",
    )
    auth: AuthConfig = Field(
        default_factory=AuthConfig,
        title="认证配置",
        description="JWT、会话、二次验证与 Turnstile 配置。",
    )
    sms: SmsConfig = Field(
        default_factory=SmsConfig,
        title="短信配置",
        description="腾讯云短信验证码配置。",
    )
    oauth: OAuthConfig = Field(
        default_factory=OAuthConfig,
        title="OAuth 配置",
        description="GitHub、Google 登录和 OAuth ticket 配置。",
    )
    mall: MallConfig = Field(
        default_factory=MallConfig,
        title="商城配置",
        description="商城订单超时、自动收货、保证金与微信支付配置。",
    )
    compliance: ComplianceConfig = Field(
        default_factory=ComplianceConfig,
        title="合规配置",
        description="网站主体、协议版本、材料留存与敏感字段加密配置。",
    )

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del env_settings, dotenv_settings, file_secret_settings
        return (
            init_settings,
            LegacyEnvironmentSettingsSource(settings_cls, os.environ),
            LegacyEnvironmentSettingsSource(settings_cls, _dotenv_values()),
            RequiredTomlConfigSettingsSource(settings_cls),
        )


def _legacy_init_values(data: dict[str, Any]) -> dict[str, Any]:
    """Accept historic flat constructor fields for tests and maintenance tools."""
    nested = dict(data)
    for section, fields in ENVIRONMENT_FIELDS.items():
        section_values = dict(nested.get(section, {}))
        for environment_name, field_name in fields.items():
            flat_name = environment_name.lower()
            if flat_name in nested:
                section_values[field_name] = nested.pop(flat_name)
        if section_values:
            nested[section] = section_values
    return nested


class GlobalConfig(SystemConfig):
    """Backward-compatible constructor name for :class:`SystemConfig`."""

    def __init__(self, **data: Any) -> None:
        super().__init__(**_legacy_init_values(data))


global_config = GlobalConfig()

__all__ = [
    "AppConfig",
    "AuthConfig",
    "ComplianceConfig",
    "DatabaseConfig",
    "FilesConfig",
    "GlobalConfig",
    "MailConfig",
    "OAuthConfig",
    "SystemConfig",
    "global_config",
]
