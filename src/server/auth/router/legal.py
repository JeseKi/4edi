"""公开法律文档和登录用户协议确认接口。"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Query, Request, Security

from src.server.auth.dependencies import AuthenticatedPrincipal, get_current_principal
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.compliance import get_legal_document, list_legal_documents
from src.server.database_executor import DatabaseExecutor, get_database_executor

from ..schemas import LegalAcceptanceIn, LegalAcceptanceStatusOut, LegalDocumentOut
from ..service import short_transactions
from .base import router


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else None


@router.get("/legal-documents", response_model=list[LegalDocumentOut], summary="当前法律文档")
async def legal_documents():
    return list_legal_documents()


@router.get(
    "/legal-documents/{document_type}",
    response_model=LegalDocumentOut,
    summary="法律文档详情",
)
async def legal_document(document_type: str, version: str | None = Query(default=None)):
    try:
        return get_legal_document(document_type, version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc


@router.get(
    "/legal-acceptances/me",
    response_model=LegalAcceptanceStatusOut,
    summary="我的协议确认状态",
)
async def my_legal_acceptances(
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: short_transactions.current_acceptance_status(db, current_user.user_id)
    )


@router.post(
    "/legal-acceptances/me",
    response_model=LegalAcceptanceStatusOut,
    summary="确认当前用户协议与隐私政策",
)
async def accept_current_legal_documents(
    request: Request,
    payload: LegalAcceptanceIn,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _accept(db):
        short_transactions.record_user_acceptances(
            db,
            user_id=current_user.user_id,
            user_agreement_version=payload.user_agreement_version,
            privacy_policy_version=payload.privacy_policy_version,
            client_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        return short_transactions.current_acceptance_status(db, current_user.user_id)

    return await database_executor.run(_accept)
