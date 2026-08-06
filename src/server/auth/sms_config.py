"""短信配置模型与共享配置访问器。"""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field


class SmsConfig(BaseModel):
    secret_id: str = Field(
        default="", title="腾讯云 SecretId", description="腾讯云账号 SecretId。"
    )
    secret_key: str = Field(
        default="", title="腾讯云 SecretKey", description="腾讯云账号 SecretKey。"
    )
    sdk_app_id: str = Field(
        default="", title="短信应用 ID", description="腾讯云短信 SDKAppID。"
    )
    sign_name: str = Field(
        default="", title="短信签名", description="腾讯云短信签名名称。"
    )
    template_id: str = Field(
        default="", title="短信模板 ID", description="腾讯云短信验证码模板 ID。"
    )
    region: str = Field(
        default="ap-guangzhou",
        title="短信地域",
        description="腾讯云短信服务地域。",
    )
    endpoint: str = Field(
        default="sms.tencentcloudapi.com",
        title="短信接口地址",
        description="腾讯云短信 API 接入点。",
    )
    timeout_seconds: int = Field(
        default=10,
        ge=1,
        le=60,
        title="短信请求超时",
        description="腾讯云短信请求的最长秒数。",
    )


if TYPE_CHECKING:
    sms_config: SmsConfig


def __getattr__(name: str) -> Any:
    if name == "sms_config":
        from src.server.config import global_config

        return global_config.sms
    raise AttributeError(name)


__all__ = ["SmsConfig", "sms_config"]
