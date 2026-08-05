from __future__ import annotations

import mimetypes
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import PurePath

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.dependencies import AuthenticatedPrincipal, is_administrative_role
from src.server.config import global_config
from src.server.task_runtime import TaskReference, TaskRuntime

from ..dao import FileAssetDAO
from ..models import FileAsset
from ..schemas import FileAssetOut, FileUploadIntentCreate
from ..storage import FileStorage, LocalFileStorage, StoredObject
from .long_tasks import DELETE_FILE_OBJECT, EXPIRE_PENDING_FILE

STATUS_PENDING = "pending_upload"
STATUS_AVAILABLE = "available"
STATUS_EXPIRED = "expired"
STATUS_REJECTED = "rejected"
STATUS_DELETION_PENDING = "deletion_pending"
STATUS_DELETED = "deleted"

# 客户端 MIME 在 WPS、浏览器和各操作系统之间并不可靠；上传准入以扩展名白名单为准。
FILE_EXTENSION_MEDIA_TYPES = {
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".webp": "image/webp",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass(frozen=True)
class FileAssetSnapshot:
    id: str
    storage_key: str
    storage_driver: str
    original_filename: str
    content_type: str
    size_bytes: int
    status: str


def _safe_filename(value: str) -> str:
    name = PurePath(value.replace("\\", "/")).name.strip().replace("\x00", "")
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=422, detail="文件名无效")
    return name[:255]


def _resolve_content_type(filename: str) -> str:
    extension = PurePath(filename).suffix.lower()
    if extension not in global_config.files.allowed_extensions:
        display_type = extension.removeprefix(".").upper() if extension else "无扩展名"
        raise HTTPException(status_code=422, detail=f"不支持 {display_type} 文件类型.")
    return FILE_EXTENSION_MEDIA_TYPES.get(extension) or mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _storage_key(asset_id: str, filename: str) -> str:
    """Keep the extension on stored objects so local development tools recognize them."""
    return f"file-assets/{asset_id}{PurePath(filename).suffix.lower()}"


def _is_admin(principal: AuthenticatedPrincipal) -> bool:
    return is_administrative_role(principal.role)


def _assert_access(asset: FileAsset, principal: AuthenticatedPrincipal) -> None:
    if asset.created_by_user_id != principal.user_id and not _is_admin(principal):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")


def _to_out(asset: FileAsset) -> FileAssetOut:
    return FileAssetOut.model_validate(asset)


def _is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= datetime.now(timezone.utc)


def create_upload_intent(
    db: Session,
    runtime: TaskRuntime,
    payload: FileUploadIntentCreate,
    principal: AuthenticatedPrincipal,
) -> FileAsset:
    filename = _safe_filename(payload.filename)
    content_type = _resolve_content_type(filename)
    if payload.size_bytes > global_config.files.max_upload_bytes:
        raise HTTPException(status_code=422, detail="文件超过允许大小")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=global_config.files.upload_ttl_minutes)
    asset_id = secrets.token_hex(16)
    asset = FileAssetDAO(db).create(
        id=asset_id,
        created_by_user_id=principal.user_id,
        storage_driver=global_config.files.storage_driver,
        storage_key=_storage_key(asset_id, filename),
        original_filename=filename,
        content_type=content_type,
        size_bytes=payload.size_bytes,
        status=STATUS_PENDING,
        scan_status="not_requested",
        upload_expires_at=expires_at,
    )
    runtime.enqueue(
        db,
        EXPIRE_PENDING_FILE,
        asset_id,
        reference=TaskReference(resource_type="file_asset", resource_id=asset_id),
        not_before=expires_at,
    )
    return asset


def _get_authorized_asset(
    db: Session, asset_id: str, principal: AuthenticatedPrincipal
) -> FileAsset:
    asset = FileAssetDAO(db).get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    _assert_access(asset, principal)
    return asset


def get_asset(db: Session, asset_id: str, principal: AuthenticatedPrincipal) -> FileAsset:
    asset = _get_authorized_asset(db, asset_id, principal)
    if asset.status != STATUS_AVAILABLE:
        raise HTTPException(status_code=404, detail="文件不存在")
    return asset


def list_assets(
    db: Session, principal: AuthenticatedPrincipal, offset: int, limit: int, owner_user_id: int | None
) -> tuple[list[FileAsset], int]:
    if owner_user_id is not None and not _is_admin(principal):
        raise HTTPException(status_code=403, detail="无权查看其他用户文件")
    owner = owner_user_id if _is_admin(principal) else principal.user_id
    return FileAssetDAO(db).list_for_user(user_id=owner, offset=offset, limit=limit)


def get_snapshot_for_upload(
    db: Session, asset_id: str, principal: AuthenticatedPrincipal
) -> FileAssetSnapshot:
    asset = _get_authorized_asset(db, asset_id, principal)
    if asset.status != STATUS_PENDING:
        raise HTTPException(status_code=409, detail="文件不处于待上传状态")
    if _is_expired(asset.upload_expires_at):
        raise HTTPException(status_code=409, detail="上传意图已过期")
    return FileAssetSnapshot(
        id=asset.id,
        storage_key=asset.storage_key,
        storage_driver=asset.storage_driver,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        status=asset.status,
    )


def get_snapshot_for_download(
    db: Session, asset_id: str, principal: AuthenticatedPrincipal
) -> FileAssetSnapshot:
    asset = get_asset(db, asset_id, principal)
    return FileAssetSnapshot(
        id=asset.id,
        storage_key=asset.storage_key,
        storage_driver=asset.storage_driver,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        status=asset.status,
    )


def store_local_upload(snapshot: FileAssetSnapshot, source, storage: FileStorage) -> None:
    if not isinstance(storage, LocalFileStorage):
        raise HTTPException(status_code=409, detail="当前存储模式不接受服务端上传")
    actual_size = storage.write_from_file(snapshot.storage_key, source, snapshot.size_bytes)
    if actual_size != snapshot.size_bytes:
        storage.delete(snapshot.storage_key)
        raise HTTPException(status_code=422, detail="上传文件大小与上传意图不一致")


def finalize_upload(
    db: Session,
    runtime: TaskRuntime,
    principal: AuthenticatedPrincipal,
    asset_id: str,
    stored: StoredObject,
) -> tuple[FileAssetOut, str | None]:
    asset = _get_authorized_asset(db, asset_id, principal)
    if asset.status == STATUS_AVAILABLE:
        return _to_out(asset), None
    if asset.status != STATUS_PENDING or _is_expired(asset.upload_expires_at):
        raise HTTPException(status_code=409, detail="文件不处于可确认状态")

    invalid_reason = None
    if stored.size_bytes != asset.size_bytes:
        invalid_reason = "对象存储中的文件大小与上传意图不一致"

    if invalid_reason:
        asset.status = STATUS_REJECTED
        runtime.enqueue(
            db,
            DELETE_FILE_OBJECT,
            asset.id,
            reference=TaskReference(resource_type="file_asset", resource_id=asset.id),
        )
        db.flush()
        return _to_out(asset), invalid_reason

    asset.status = STATUS_AVAILABLE
    asset.uploaded_at = datetime.now(timezone.utc)
    db.flush()
    return _to_out(asset), None


def mark_for_deletion(
    db: Session, runtime: TaskRuntime, asset_id: str, principal: AuthenticatedPrincipal
) -> FileAssetOut:
    asset = _get_authorized_asset(db, asset_id, principal)
    if asset.status == STATUS_DELETED:
        return _to_out(asset)
    if asset.status != STATUS_DELETION_PENDING:
        asset.status = STATUS_DELETION_PENDING
        runtime.enqueue(
            db,
            DELETE_FILE_OBJECT,
            asset.id,
            reference=TaskReference(resource_type="file_asset", resource_id=asset.id),
        )
    db.flush()
    return _to_out(asset)


def mark_expired_if_pending(db: Session, asset_id: str) -> FileAssetSnapshot | None:
    asset = FileAssetDAO(db).get(asset_id)
    if asset is None or asset.status != STATUS_PENDING:
        return None
    if not _is_expired(asset.upload_expires_at):
        return None
    asset.status = STATUS_EXPIRED
    db.flush()
    return FileAssetSnapshot(
        id=asset.id, storage_key=asset.storage_key, storage_driver=asset.storage_driver,
        original_filename=asset.original_filename, content_type=asset.content_type,
        size_bytes=asset.size_bytes, status=asset.status,
    )


def get_deletion_snapshot(db: Session, asset_id: str) -> FileAssetSnapshot | None:
    asset = FileAssetDAO(db).get(asset_id)
    if asset is None or asset.status not in {STATUS_DELETION_PENDING, STATUS_REJECTED, STATUS_EXPIRED}:
        return None
    return FileAssetSnapshot(
        id=asset.id, storage_key=asset.storage_key, storage_driver=asset.storage_driver,
        original_filename=asset.original_filename, content_type=asset.content_type,
        size_bytes=asset.size_bytes, status=asset.status,
    )


def mark_deleted(db: Session, asset_id: str) -> None:
    asset = FileAssetDAO(db).get(asset_id)
    if asset and asset.status in {STATUS_DELETION_PENDING, STATUS_REJECTED}:
        asset.status = STATUS_DELETED
        asset.deleted_at = datetime.now(timezone.utc)
