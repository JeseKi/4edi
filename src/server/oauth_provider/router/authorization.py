# -*- coding: utf-8 -*-
"""OAuth 授权码与 Device Flow 路由。"""

from fastapi import Depends, HTTPException, Query, Request, Security

from src.server.audit import service as audit_service
from src.server.auth import service as auth_service
from src.server.auth.dao import UserDAO
from src.server.auth.dependencies import AuthenticatedPrincipal, get_current_principal
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.database_executor import DatabaseExecutor, get_database_executor

from .. import service
from ..schemas import (
    OAuthAuthorizeConfirm, OAuthAuthorizeMetadata, OAuthAuthorizeResult,
    OAuthDeviceAuthorizationConfirm, OAuthDeviceAuthorizationMetadata,
    OAuthDeviceAuthorizationResponse, OAuthDeviceAuthorizationResult,
)
from . import router
from .helpers import read_urlencoded_form, resolve_client_credentials


@router.get("/authorize/metadata", response_model=OAuthAuthorizeMetadata, summary="获取 OAuth 授权请求元数据")
async def authorize_metadata(
    response_type: str = Query(...), client_id: str = Query(...), redirect_uri: str = Query(...),
    scope: str = Query(default=""), state: str | None = Query(default=None),
    code_challenge: str | None = Query(default=None), code_challenge_method: str | None = Query(default="S256"),
    _: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    result = await database_executor.run(lambda db: service.get_authorize_metadata(
        db, response_type=response_type, client_id=client_id, redirect_uri=redirect_uri,
        scope=scope, state=state, code_challenge=code_challenge, code_challenge_method=code_challenge_method,
    ))
    return OAuthAuthorizeMetadata.model_validate(result)


@router.post("/authorize", response_model=OAuthAuthorizeResult, summary="确认 OAuth 授权并生成跳转地址")
async def authorize(
    request: Request, payload: OAuthAuthorizeConfirm,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="oauth.authorization.approve" if payload.approve else "oauth.authorization.deny",
        resource_type="oauth_client", resource_id=payload.client_id,
        target_summary=f"OAuth Client {payload.client_id}",
        detail={"requested_scopes": list(auth_service.normalize_scopes(payload.scope))},
    )
    def _authorize(db) -> OAuthAuthorizeResult:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="未认证或令牌无效")
        return OAuthAuthorizeResult(
            redirect_url=service.create_authorization_redirect(db, payload, user)
        )

    return await database_executor.run(_authorize)


@router.post("/device_authorization", response_model=OAuthDeviceAuthorizationResponse, summary="OAuth Device Authorization Endpoint")
async def device_authorization(
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    form = await read_urlencoded_form(request)
    client_id, _ = resolve_client_credentials(request, form)
    audit_service.attach_audit_context(
        request.state, action="oauth.device_code.create", resource_type="oauth_client",
        resource_id=client_id, target_summary=f"OAuth Client {client_id}",
        detail={"requested_scopes": list(auth_service.normalize_scopes(form.get("scope", "")))},
    )
    result = await database_executor.run(
        lambda db: service.create_device_authorization(
            db, client_id=client_id, scope=form.get("scope", "")
        )
    )
    return OAuthDeviceAuthorizationResponse.model_validate(result)


@router.get("/device/metadata", response_model=OAuthDeviceAuthorizationMetadata, summary="获取 OAuth Device 授权请求元数据")
async def device_authorization_metadata(
    user_code: str = Query(...),
    _: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    result = await database_executor.run(
        lambda db: service.get_device_authorization_metadata(db, user_code=user_code)
    )
    return OAuthDeviceAuthorizationMetadata.model_validate(result)


@router.post("/device/authorize", response_model=OAuthDeviceAuthorizationResult, summary="确认 OAuth Device 授权")
async def device_authorize(
    request: Request, payload: OAuthDeviceAuthorizationConfirm,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="oauth.device_authorization.approve" if payload.approve else "oauth.device_authorization.deny",
        resource_type="oauth_device_authorization", target_summary="OAuth Device 授权",
    )
    def _confirm(db) -> dict:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="未认证或令牌无效")
        return service.confirm_device_authorization(
            db, user_code=payload.user_code, approve=payload.approve, user=user
        )

    result = await database_executor.run(_confirm)
    audit_service.attach_audit_context(
        request.state, resource_type="oauth_client", resource_id=result["client_id"],
        target_summary=f"OAuth Client {result['client_id']}", detail={"approved_scopes": result["scopes"]},
    )
    return OAuthDeviceAuthorizationResult.model_validate(result)
