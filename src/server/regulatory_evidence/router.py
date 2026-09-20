from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Security, status
from fastapi.responses import FileResponse, RedirectResponse, Response

from src.server.audit import service as audit_service
from src.server.auth.dependencies.admin import get_current_admin
from src.server.auth.dependencies.current_user import AuthenticatedPrincipal
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.files.schemas import FILE_ASSET_ID_PATTERN
from src.server.files.storage import (
    FileObjectNotFoundError,
    LocalFileStorage,
    S3FileStorage,
    get_file_storage,
)

from . import service
from .schemas import (
    EvidenceLinkCreateIn,
    EvidenceLinkCreatedOut,
    EvidenceLinkOut,
    RegulatoryEvidenceOut,
)

admin_router = APIRouter(
    prefix="/api/regulatory-evidence/admin", tags=["监管取证-管理员"]
)
public_router = APIRouter(prefix="/api/regulatory-evidence", tags=["监管取证"])

EvidenceType = Literal["publisher_verification", "shop_qualification"]
EvidenceToken = Annotated[
    str,
    Header(
        alias="X-Regulatory-Evidence-Token",
        min_length=32,
        max_length=32,
    ),
]


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Referrer-Policy"] = "no-referrer"


@admin_router.post(
    "/links",
    summary="生成不限时监管核验链接",
    response_model=EvidenceLinkCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence_link(
    payload: EvidenceLinkCreateIn,
    request: Request,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db):
        link, token = service.create_link(
            db,
            evidence_type=payload.evidence_type,
            resource_id=payload.resource_id,
            created_by_user_id=current_admin.user_id,
        )
        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="regulatory_evidence.link.create",
            resource_type=payload.evidence_type,
            resource_id=payload.resource_id,
            detail={"link_id": link.id, "token_hint": link.token_hint},
        )
        data = EvidenceLinkOut.model_validate(link).model_dump()
        return {**data, "token": token, "share_path": f"/regulatory-evidence#{token}"}

    return await database_executor.run(_create)


@admin_router.get(
    "/links", summary="监管核验链接列表", response_model=list[EvidenceLinkOut]
)
async def list_evidence_links(
    evidence_type: EvidenceType,
    resource_id: int = Query(..., ge=1),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [
            EvidenceLinkOut.model_validate(link)
            for link in service.list_links(
                db, evidence_type=evidence_type, resource_id=resource_id
            )
        ]
    )


@admin_router.post(
    "/links/{link_id}/revoke",
    summary="吊销监管核验链接",
    response_model=EvidenceLinkOut,
)
async def revoke_evidence_link(
    link_id: int,
    request: Request,
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _revoke(db):
        link = service.revoke_link(db, link_id)
        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="regulatory_evidence.link.revoke",
            resource_type=link.evidence_type,
            resource_id=link.resource_id,
            detail={"link_id": link.id, "token_hint": link.token_hint},
        )
        return EvidenceLinkOut.model_validate(link)

    return await database_executor.run(_revoke)


@public_router.get("", summary="通过核验令牌查看监管取证材料", response_model=RegulatoryEvidenceOut)
async def get_regulatory_evidence(
    response: Response,
    token: EvidenceToken,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    payload = await database_executor.run(
        lambda db: service.get_evidence_payload(db, token)
    )
    _no_store(response)
    return payload


@public_router.get("/assets/{asset_id}", summary="查看监管取证材料文件")
async def get_regulatory_evidence_asset(
    asset_id: Annotated[str, Path(pattern=FILE_ASSET_ID_PATTERN)],
    token: EvidenceToken,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    snapshot = await database_executor.run(
        lambda db: service.get_evidence_asset_snapshot(db, token, asset_id)
    )
    storage = get_file_storage()
    try:
        if isinstance(storage, LocalFileStorage):
            file_response = FileResponse(
                storage.path_for_download(snapshot.storage_key),
                media_type=snapshot.content_type,
                filename=snapshot.original_filename,
                content_disposition_type="inline",
            )
            _no_store(file_response)
            return file_response
        if isinstance(storage, S3FileStorage):
            redirect_response = RedirectResponse(
                storage.download_url(snapshot.storage_key, snapshot.original_filename),
                status_code=307,
            )
            _no_store(redirect_response)
            return redirect_response
    except FileObjectNotFoundError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="文件对象不存在") from exc
    from fastapi import HTTPException

    raise HTTPException(status_code=500, detail="不支持的文件存储驱动")
