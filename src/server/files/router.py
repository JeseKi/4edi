from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Security, status
from fastapi.responses import FileResponse, RedirectResponse
from starlette.datastructures import UploadFile

from src.server.audit import service as audit_service
from src.server.auth.dependencies import AuthenticatedPrincipal, get_current_principal
from src.server.auth.service.scopes import SCOPE_FILES_READ, SCOPE_FILES_WRITE
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.task_runtime import TaskRuntime, get_task_runtime

from . import service
from .schemas import (
    FILE_ASSET_ID_PATTERN,
    FileAssetListOut,
    FileAssetOut,
    FileUploadIntentCreate,
    FileUploadIntentOut,
    LocalUploadTarget,
    S3PostUploadTarget,
)
from .storage import FileObjectNotFoundError, LocalFileStorage, S3FileStorage, get_file_storage

router = APIRouter(prefix="/api/files", tags=["文件"])


@router.post("/upload-intents", response_model=FileUploadIntentOut, status_code=status.HTTP_201_CREATED, summary="创建文件上传意图")
async def create_upload_intent(
    payload: FileUploadIntentCreate,
    request: Request,
    runtime: TaskRuntime = Depends(get_task_runtime),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_FILES_WRITE]),
):
    asset_out, snapshot = await database_executor.run(
        lambda db: _create_upload_intent_out(db, runtime, payload, principal)
    )
    audit_service.attach_audit_context(
        request.state,
        action="files.upload_intent.create",
        resource_type="file_asset",
        resource_id=asset_out.id,
        detail={"size_bytes": asset_out.size_bytes},
    )
    storage = get_file_storage()
    if isinstance(storage, LocalFileStorage):
        return FileUploadIntentOut(
            asset=asset_out,
            # 前端 Axios 已以 /api 为 baseURL，避免拼成 /api/api/files/...。
            upload=LocalUploadTarget(url=f"/files/{asset_out.id}/content"),
        )
    if isinstance(storage, S3FileStorage):
        target = storage.create_upload_target(snapshot.storage_key, snapshot.content_type, snapshot.size_bytes)
        return FileUploadIntentOut(
            asset=asset_out,
            upload=S3PostUploadTarget(url=target["url"], fields=target["fields"]),
        )
    raise HTTPException(status_code=500, detail="不支持的文件存储驱动")


@router.post("/{asset_id}/content", status_code=status.HTTP_204_NO_CONTENT, summary="上传文件内容")
async def upload_local_content(
    asset_id: Annotated[str, Path(pattern=FILE_ASSET_ID_PATTERN)],
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_FILES_WRITE]),
):
    snapshot = await database_executor.run(
        lambda db: service.get_snapshot_for_upload(db, asset_id, principal)
    )
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(status_code=422, detail="请使用 file 字段上传文件")
    service.store_local_upload(
        snapshot,
        upload.file,
        get_file_storage(),
    )
    audit_service.attach_audit_context(
        request.state,
        action="files.content.upload",
        resource_type="file_asset",
        resource_id=asset_id,
    )


@router.post("/{asset_id}/complete", response_model=FileAssetOut, summary="完成文件上传")
async def complete_upload(
    asset_id: str,
    request: Request,
    runtime: TaskRuntime = Depends(get_task_runtime),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_FILES_WRITE]),
):
    snapshot = await database_executor.run(
        lambda db: service.get_snapshot_for_upload(db, asset_id, principal)
    )
    storage = get_file_storage()
    if snapshot.storage_driver != storage.driver:
        raise HTTPException(status_code=409, detail="文件存储配置已变更，无法确认上传")
    try:
        stored = storage.inspect(snapshot.storage_key)
    except FileObjectNotFoundError as exc:
        raise HTTPException(status_code=400, detail="尚未检测到上传对象") from exc
    result, invalid_reason = await database_executor.run(
        lambda db: service.finalize_upload(
            db, runtime, principal, asset_id, stored
        )
    )
    audit_service.attach_audit_context(
        request.state,
        action="files.upload.complete",
        resource_type="file_asset",
        resource_id=asset_id,
        detail={"size_bytes": snapshot.size_bytes},
    )
    if invalid_reason:
        raise HTTPException(status_code=422, detail=invalid_reason)
    return result


@router.get("", response_model=FileAssetListOut, summary="查询文件列表")
async def list_file_assets(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    owner_user_id: int | None = Query(default=None, ge=1),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_FILES_READ]),
):
    return await database_executor.run(
        lambda db: _list_assets_out(db, principal, offset, limit, owner_user_id)
    )


@router.get("/{asset_id}", response_model=FileAssetOut, summary="获取文件详情")
async def get_file_asset(
    asset_id: str,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_FILES_READ]),
):
    return await database_executor.run(
        lambda db: FileAssetOut.model_validate(service.get_asset(db, asset_id, principal))
    )


@router.get("/{asset_id}/download", summary="下载文件")
async def download_file_asset(
    asset_id: str,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_FILES_READ]),
):
    snapshot = await database_executor.run(
        lambda db: service.get_snapshot_for_download(db, asset_id, principal)
    )
    storage = get_file_storage()
    try:
        if isinstance(storage, LocalFileStorage):
            return FileResponse(
                storage.path_for_download(snapshot.storage_key),
                media_type=snapshot.content_type,
                filename=snapshot.original_filename,
                content_disposition_type="attachment",
            )
        if isinstance(storage, S3FileStorage):
            return RedirectResponse(storage.download_url(snapshot.storage_key, snapshot.original_filename), status_code=307)
    except FileObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="文件对象不存在") from exc
    raise HTTPException(status_code=500, detail="不支持的文件存储驱动")


@router.delete("/{asset_id}", response_model=FileAssetOut, summary="删除文件")
async def delete_file_asset(
    asset_id: str,
    request: Request,
    runtime: TaskRuntime = Depends(get_task_runtime),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_FILES_WRITE]),
):
    asset = await database_executor.run(
        lambda db: service.mark_for_deletion(db, runtime, asset_id, principal)
    )
    audit_service.attach_audit_context(
        request.state, action="files.delete", resource_type="file_asset", resource_id=asset_id
    )
    return asset


def _create_upload_intent_out(db, runtime, payload, principal):
    asset = service.create_upload_intent(db, runtime, payload, principal)
    return FileAssetOut.model_validate(asset), service.FileAssetSnapshot(
        id=asset.id,
        storage_key=asset.storage_key,
        storage_driver=asset.storage_driver,
        original_filename=asset.original_filename,
        content_type=asset.content_type,
        size_bytes=asset.size_bytes,
        status=asset.status,
    )


def _list_assets_out(db, principal, offset: int, limit: int, owner_user_id: int | None) -> FileAssetListOut:
    items, total = service.list_assets(db, principal, offset, limit, owner_user_id)
    return FileAssetListOut(
        items=[FileAssetOut.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )
