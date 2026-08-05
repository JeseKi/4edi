"""Mail configuration model and shared-settings accessor."""

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, EmailStr, Field


class MailConfig(BaseModel):
    executor_max_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        title="邮件执行槽位",
        description="Web 请求异步投递邮件的最大并发数。",
    )
    executor_queue_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        title="邮件排队超时",
        description="等待邮件执行槽位的最长秒数。",
    )
    smtp_host: str = Field(
        default="smtp.example.com",
        title="SMTP 主机",
        description="SMTP 服务的主机名或 IP 地址。",
    )
    smtp_port: int = Field(
        default=465, title="SMTP 端口", description="SMTP 服务端口。"
    )
    use_ssl: bool = Field(
        default=True, title="SMTP SSL", description="是否使用隐式 SSL 连接 SMTP。"
    )
    use_tls: bool = Field(
        default=False,
        title="SMTP TLS",
        description="是否在连接后通过 STARTTLS 升级 SMTP 连接。",
    )
    timeout: int = Field(
        default=5, title="SMTP 超时", description="SMTP 网络操作的最长秒数。"
    )
    sender_email: EmailStr | None = Field(
        default=None, title="发件人邮箱", description="发送邮件时使用的 From 邮箱地址。"
    )
    sender_password: str | None = Field(
        default=None, title="发件人密码", description="SMTP 认证密码或应用专用密码。"
    )
    sender_name: str | None = Field(
        default=None, title="发件人名称", description="邮件中显示的发件人名称。"
    )


if TYPE_CHECKING:
    mail_config: MailConfig


def __getattr__(name: str) -> Any:
    if name == "mail_config":
        from src.server.config import global_config

        return global_config.mail
    raise AttributeError(name)


__all__ = ["MailConfig", "mail_config"]
