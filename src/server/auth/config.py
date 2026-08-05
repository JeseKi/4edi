"""Authentication configuration model and shared-settings accessor."""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    jwt_secret_key: str = Field(
        default="dev_secret_key_for_testing_only",
        title="JWT 密钥",
        description="JWT 签名密钥；生产环境必须通过环境变量提供。",
    )
    jwt_algorithm: str = Field(
        default="HS256", title="JWT 算法", description="JWT 的签名算法。"
    )
    access_token_ttl_minutes: int = Field(
        default=15,
        title="Access Token 有效期",
        description="Access Token 的有效分钟数。",
    )
    refresh_token_ttl_days: int = Field(
        default=7,
        title="Refresh Token 有效期",
        description="Refresh Token 的有效天数。",
    )
    refresh_cookie_name: str = Field(
        default="fullstack_template_refresh_token",
        title="刷新 Cookie 名称",
        description="保存 Refresh Token 的 Cookie 名称。",
    )
    refresh_cookie_samesite: str = Field(
        default="lax",
        title="刷新 Cookie SameSite",
        description="Refresh Token Cookie 的 SameSite 策略。",
    )
    refresh_cookie_secure: bool = Field(
        default=False,
        title="刷新 Cookie Secure",
        description="是否只通过 HTTPS 发送 Refresh Token Cookie。",
    )
    test_token: str = Field(
        default="KISPACE_TEST_TOKEN",
        title="测试 Token",
        description="开发和测试环境的便捷鉴权 Token。",
    )
    init_admin_name: str = Field(
        default="admin",
        title="初始管理员用户名",
        description="首次初始化数据库时创建的管理员用户名。",
    )
    init_admin_password: str = Field(
        default="admin123",
        title="初始管理员密码",
        description="首次初始化数据库时创建的管理员密码；生产必须覆盖。",
    )
    init_admin_email: str = Field(
        default="admin@example.com",
        title="初始管理员邮箱",
        description="首次初始化数据库时创建的管理员邮箱。",
    )
    two_factor_challenge_ttl_minutes: int = Field(
        default=5, title="2FA 挑战有效期", description="二次验证登录挑战的有效分钟数。"
    )
    two_factor_setup_ttl_minutes: int = Field(
        default=10, title="2FA 设置有效期", description="两步验证绑定确认的有效分钟数。"
    )
    two_factor_issuer_name: str = Field(
        default="Fullstack Template",
        title="TOTP 签发方",
        description="显示在验证器应用中的 TOTP 签发方名称。",
    )
    two_factor_encryption_key: str = Field(
        default="fullstack-template-2fa-dev-key-change-me",
        title="2FA 加密密钥",
        description="加密存储 TOTP secret 的密钥；生产必须覆盖。",
    )
    two_factor_backup_code_count: int = Field(
        default=8, title="备份码数量", description="每次生成的两步验证备份码数量。"
    )
    two_factor_max_verify_attempts: int = Field(
        default=5,
        title="2FA 最大尝试次数",
        description="单个两步验证挑战允许的最大失败次数。",
    )
    turnstile_enabled: bool = Field(
        default=False,
        title="启用 Turnstile",
        description="是否验证 Cloudflare Turnstile 人机校验。",
    )
    turnstile_secret_key: str = Field(
        default="",
        title="Turnstile 密钥",
        description="Cloudflare Turnstile 服务端密钥；启用时必填。",
    )
    turnstile_verify_timeout_seconds: int = Field(
        default=4,
        title="Turnstile 校验超时",
        description="请求 Turnstile 校验接口的最长秒数。",
    )


if TYPE_CHECKING:
    auth_config: AuthConfig


def __getattr__(name: str) -> Any:
    if name == "auth_config":
        from src.server.config import global_config

        return global_config.auth
    raise AttributeError(name)


__all__ = ["AuthConfig", "auth_config"]
