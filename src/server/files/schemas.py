from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FILE_ASSET_ID_PATTERN = r"^[a-f0-9]{32}$"
FileAssetStatus = Literal[
    "pending_upload", "available", "expired", "rejected", "deletion_pending", "deleted", "quarantined"
]


class FileUploadIntentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)


class LocalUploadTarget(BaseModel):
    kind: Literal["local"] = "local"
    method: Literal["POST"] = "POST"
    url: str


class S3PostUploadTarget(BaseModel):
    kind: Literal["s3_post"] = "s3_post"
    method: Literal["POST"] = "POST"
    url: str
    fields: dict[str, str]


class FileAssetOut(BaseModel):
    id: str = Field(pattern=FILE_ASSET_ID_PATTERN)
    created_by_user_id: int
    original_filename: str
    size_bytes: int
    status: FileAssetStatus
    scan_status: str
    upload_expires_at: datetime
    uploaded_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileUploadIntentOut(BaseModel):
    asset: FileAssetOut
    upload: LocalUploadTarget | S3PostUploadTarget


class FileAssetListOut(BaseModel):
    items: list[FileAssetOut]
    total: int
    offset: int
    limit: int
