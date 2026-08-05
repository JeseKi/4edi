"""File-assets configuration section."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator


DEFAULT_FILE_ALLOWED_EXTENSIONS = [
    ".csv",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pptx",
    ".txt",
    ".webp",
    ".xlsx",
]


class FilesConfig(BaseModel):
    storage_driver: str = Field(
        default="local",
        pattern="^(local|s3)$",
        title="文件存储驱动",
        description="文件资产使用本地磁盘或 S3 兼容对象存储。",
    )
    local_root: Path = Field(
        default=Path("data") / "uploads",
        title="本地存储目录",
        description="local 驱动保存上传对象的相对或绝对目录。",
    )
    s3_bucket: str = Field(
        default="",
        title="S3 Bucket",
        description="S3 或兼容对象存储使用的 Bucket 名称。",
    )
    s3_region: str = Field(
        default="us-east-1", title="S3 区域", description="S3 客户端使用的区域名称。"
    )
    s3_endpoint_url: str = Field(
        default="",
        title="S3 Endpoint",
        description="可选的 S3 兼容对象存储 Endpoint URL。",
    )
    s3_access_key_id: str = Field(
        default="",
        title="S3 Access Key ID",
        description="S3 访问凭据 ID；生产通过环境变量提供。",
    )
    s3_secret_access_key: str = Field(
        default="",
        title="S3 Secret Access Key",
        description="S3 访问密钥；生产通过环境变量提供。",
    )
    s3_addressing_style: str = Field(
        default="auto",
        pattern="^(auto|path|virtual)$",
        title="S3 寻址方式",
        description="S3 请求使用 auto、path 或 virtual 寻址。",
    )
    presign_ttl_seconds: int = Field(
        default=900,
        ge=60,
        le=3600,
        title="预签名 URL 有效期",
        description="下载和直传预签名 URL 的有效秒数。",
    )
    upload_ttl_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        title="上传意图有效期",
        description="等待完成的文件上传意图有效分钟数。",
    )
    max_upload_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
        le=5 * 1024 * 1024 * 1024,
        title="最大上传大小",
        description="单个文件上传允许的最大字节数。",
    )
    allowed_extensions: list[str] = Field(
        default_factory=lambda: list(DEFAULT_FILE_ALLOWED_EXTENSIONS),
        title="允许文件扩展名",
        description="允许用户上传的文件扩展名白名单。",
    )

    @field_validator("allowed_extensions", mode="after")
    @classmethod
    def normalize_extensions(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for extension in values:
            value = str(extension).strip()
            if value:
                normalized.append(value if value.startswith(".") else f".{value}")
        return normalized
