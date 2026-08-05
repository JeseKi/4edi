"""Platform-owned sections of the shared system configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from src.server.settings_sources import PROJECT_ROOT


DEFAULT_ENABLED_FEATURES = [
    "auth",
    "admin",
    "files",
    "example",
    "frontend-error-reporting",
    "notifications",
]


def _string_values(values: list[str]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


class AppConfig(BaseModel):
    env: str = Field(default="dev", title="应用环境", description="当前运行环境名称。")
    enabled_features: list[str] = Field(
        default_factory=lambda: list(DEFAULT_ENABLED_FEATURES),
        title="启用功能包",
        description="启动时加载的功能包名称列表。",
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        title="允许跨域来源",
        description="允许调用后端 API 的浏览器 Origin 列表。",
    )
    secret_key: str = Field(
        default="dev_secret_key_for_testing_only",
        title="应用密钥",
        description="应用级签名密钥；生产环境应通过环境变量提供。",
    )
    domain: str = Field(
        default="",
        title="应用域名",
        description="用于生成密码重置等对外链接的公开域名。",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        title="HTTP 端口",
        description="Web 服务监听端口。",
    )
    project_root: Path = Field(
        default=PROJECT_ROOT,
        title="项目根目录",
        description="项目文件和相对运行目录的基准路径。",
    )

    @field_validator("enabled_features", mode="after")
    @classmethod
    def normalize_features(cls, values: list[str]) -> list[str]:
        return [value.lower() for value in _string_values(values)]

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def normalize_origins(cls, values: list[str]) -> list[str]:
        return _string_values(values) or ["*"]


class DatabaseConfig(BaseModel):
    url: str = Field(
        default="sqlite:///data/database.db",
        title="数据库连接 URL",
        description="SQLite 或 PostgreSQL 的 SQLAlchemy 连接字符串。",
    )
    pool_size: int | None = Field(
        default=None,
        ge=1,
        le=100,
        title="连接池大小",
        description="PostgreSQL Web 连接池的常驻连接数。",
    )
    max_overflow: int | None = Field(
        default=None,
        ge=0,
        le=100,
        title="连接池溢出",
        description="PostgreSQL Web 连接池允许的额外连接数。",
    )
    pool_timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        le=300,
        title="连接池等待超时",
        description="等待 PostgreSQL Web 连接的最长秒数。",
    )
    pool_recycle_seconds: int | None = Field(
        default=None,
        ge=0,
        le=86400,
        title="连接回收周期",
        description="PostgreSQL Web 连接回收前的最长存活秒数。",
    )
    executor_max_workers: int = Field(
        default=4,
        ge=1,
        le=100,
        title="短事务执行槽位",
        description="Web 数据库短事务执行器的最大并发数。",
    )
    executor_queue_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        title="短事务排队超时",
        description="短事务等待执行槽位的最长秒数。",
    )
    executor_statement_timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        title="SQL 语句超时",
        description="PostgreSQL 短事务中单条 SQL 的最长执行秒数。",
    )
    migration_retry_attempts: int = Field(
        default=30,
        ge=1,
        le=300,
        title="迁移重试次数",
        description="容器启动时 Alembic 迁移的最大重试次数。",
    )
    migration_retry_interval_seconds: int = Field(
        default=2,
        ge=1,
        le=300,
        title="迁移重试间隔",
        description="两次 Alembic 迁移尝试之间的等待秒数。",
    )


class TaskDatabaseConfig(BaseModel):
    pool_size: int = Field(
        default=2,
        ge=1,
        le=100,
        title="Worker 连接池大小",
        description="后台 worker PostgreSQL 连接池的常驻连接数。",
    )
    max_overflow: int = Field(
        default=0,
        ge=0,
        le=100,
        title="Worker 连接池溢出",
        description="后台 worker 允许额外借用的 PostgreSQL 连接数。",
    )
    pool_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=300,
        title="Worker 连接等待超时",
        description="后台 worker 等待数据库连接的最长秒数。",
    )
    pool_recycle_seconds: int = Field(
        default=1800,
        ge=0,
        le=86400,
        title="Worker 连接回收周期",
        description="后台 worker 连接回收前的最长存活秒数。",
    )


class LoggingConfig(BaseModel):
    level: str = Field(
        default="info",
        title="日志级别",
        description="应用与 worker 的最低输出日志级别。",
    )
    directory: Path = Field(
        default=Path("logs"),
        title="日志目录",
        description="相对项目根目录的日志输出目录。",
    )
    rotation: str = Field(
        default="20 MB", title="日志轮转规则", description="Loguru 文件日志轮转条件。"
    )
    retention: str = Field(
        default="14 days", title="日志保留规则", description="Loguru 文件日志保留时长。"
    )
    serialize: bool = Field(
        default=False, title="JSON 日志", description="是否以 JSON 格式序列化文件日志。"
    )


class TaskConfig(BaseModel):
    io_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        title="I/O Worker 数",
        description="I/O 队列的并发 worker 数。",
    )
    notification_workers: int = Field(
        default=2,
        ge=1,
        le=32,
        title="通知 Worker 数",
        description="通知队列的并发 worker 数。",
    )
    batch_workers: int = Field(
        default=2,
        ge=1,
        le=32,
        title="批处理 Worker 数",
        description="批处理队列的并发 worker 数。",
    )
    shutdown_timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        title="任务关闭超时",
        description="Worker 优雅停止等待任务完成的最长秒数。",
    )
    dispatch_poll_interval_seconds: float = Field(
        default=0.2,
        ge=0.05,
        le=60,
        title="任务轮询间隔",
        description="Worker 领取可执行任务的轮询间隔秒数。",
    )
    job_lease_seconds: int = Field(
        default=60,
        ge=5,
        le=86400,
        title="任务租约时长",
        description="已领取后台任务的租约秒数。",
    )
    job_heartbeat_interval_seconds: int = Field(
        default=10,
        ge=1,
        le=3600,
        title="任务心跳间隔",
        description="执行中后台任务续租的心跳间隔秒数。",
    )


class FrontendErrorReportingConfig(BaseModel):
    max_payload_bytes: int = Field(
        default=64 * 1024,
        ge=1024,
        le=1024 * 1024,
        title="前端错误最大请求体",
        description="单次前端错误上报允许的最大字节数。",
    )
    rate_limit_per_minute: int = Field(
        default=30,
        ge=1,
        le=10000,
        title="前端错误限流",
        description="每个 IP 每分钟允许的前端错误上报次数。",
    )


class NotificationsConfig(BaseModel):
    trusted_external_origins: list[str] = Field(
        default_factory=list,
        title="受信任外部来源",
        description="通知功能允许使用的外部浏览器 Origin 列表。",
    )

    @field_validator("trusted_external_origins", mode="after")
    @classmethod
    def normalize_origins(cls, values: list[str]) -> list[str]:
        return _string_values(values)
