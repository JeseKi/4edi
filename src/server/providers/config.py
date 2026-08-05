"""External-provider configuration section."""

from pydantic import BaseModel, Field, field_validator


DEFAULT_TEST_MOCK_PROVIDERS = [
    "github_oauth",
    "google_oauth",
    "turnstile",
    "mail",
    "example_external_api",
]


class ProvidersConfig(BaseModel):
    external_provider_mock_list: list[str] | None = Field(
        default=None,
        title="Mock Provider 列表",
        description="开发环境中使用本地 mock 实现的外部 Provider 名称列表。",
    )
    example_external_api_base_url: str = Field(
        default="",
        title="示例外部 API 地址",
        description="示例 real provider 请求的外部 API 基础地址。",
    )
    mock_provider_backend_url: str = Field(
        default="http://localhost:8000",
        title="Mock 配置发布地址",
        description="mock-provider 脚本发布运行时配置的后端地址。",
    )
    mock_provider_publish_interval_seconds: float = Field(
        default=2,
        ge=0.1,
        le=3600,
        title="Mock 配置发布间隔",
        description="mock-provider 脚本重复发布运行时配置的间隔秒数。",
    )

    @field_validator("external_provider_mock_list", mode="after")
    @classmethod
    def normalize_mock_list(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return [str(value).strip().lower() for value in values if str(value).strip()]

    def resolved_mock_list(self, app_env: str) -> list[str]:
        if self.external_provider_mock_list is None and app_env == "test":
            return list(DEFAULT_TEST_MOCK_PROVIDERS)
        return self.external_provider_mock_list or []
