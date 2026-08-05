"""OAuth configuration model and shared-settings accessor."""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, field_validator


class OAuthConfig(BaseModel):
    enabled_providers: list[str] = Field(
        default_factory=list,
        title="启用 OAuth 渠道",
        description="允许用户登录的 OAuth Provider 名称列表。",
    )
    github_client_id: str = Field(
        default="",
        title="GitHub Client ID",
        description="GitHub OAuth App 的公开 Client ID。",
    )
    github_client_secret: str = Field(
        default="",
        title="GitHub Client Secret",
        description="GitHub OAuth App 的 Client Secret；生产通过环境变量提供。",
    )
    github_redirect_uri: str = Field(
        default="http://localhost:8000/api/oauth/github/callback",
        title="GitHub 回调地址",
        description="GitHub OAuth 授权完成后的回调地址。",
    )
    github_scope: str = Field(
        default="read:user user:email",
        title="GitHub 授权范围",
        description="向 GitHub 请求的 OAuth Scope。",
    )
    google_client_id: str = Field(
        default="",
        title="Google Client ID",
        description="Google OAuth Client 的公开 Client ID。",
    )
    google_client_secret: str = Field(
        default="",
        title="Google Client Secret",
        description="Google OAuth Client Secret；生产通过环境变量提供。",
    )
    google_redirect_uri: str = Field(
        default="http://localhost:8000/api/oauth/google/callback",
        title="Google 回调地址",
        description="Google OAuth 授权完成后的回调地址。",
    )
    google_scope: str = Field(
        default="openid email profile",
        title="Google 授权范围",
        description="向 Google 请求的 OAuth Scope。",
    )
    oauth_ticket_ttl_minutes: int = Field(
        default=5,
        title="OAuth 票据有效期",
        description="登录回调生成的一次性 OAuth ticket 有效分钟数。",
    )
    oauth_state_ttl_minutes: int = Field(
        default=10,
        title="OAuth State 有效期",
        description="OAuth 授权请求 State 参数的有效分钟数。",
    )

    @field_validator("enabled_providers", mode="after")
    @classmethod
    def normalize_providers(cls, values: list[str]) -> list[str]:
        return [str(value).strip().upper() for value in values if str(value).strip()]


if TYPE_CHECKING:
    oauth_config: OAuthConfig


def __getattr__(name: str) -> Any:
    if name == "oauth_config":
        from src.server.config import global_config

        return global_config.oauth
    raise AttributeError(name)


__all__ = ["OAuthConfig", "oauth_config"]
