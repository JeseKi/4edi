# -*- coding: utf-8 -*-
"""OAuth token 与 userinfo 路由。"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from src.server.audit import service as audit_service
from src.server.database_executor import DatabaseExecutor, get_database_executor

from .. import service
from ..schemas import OAuthTokenResponse, OAuthUserInfo
from ..service.device import DeviceCodePollError
from . import bearer_scheme, router
from .helpers import read_urlencoded_form, required, resolve_client_credentials


@router.post("/token", response_model=OAuthTokenResponse, summary="OAuth Token Endpoint")
async def token(
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    form = await read_urlencoded_form(request)
    client_id, client_secret = resolve_client_credentials(request, form)
    grant_type = required(form, "grant_type")
    audit_service.attach_audit_context(
        request.state, action=f"oauth.token.{grant_type.replace(':', '_').replace('-', '_')}",
        resource_type="oauth_client", resource_id=client_id, target_summary=f"OAuth Client {client_id}",
        detail={"grant_type": grant_type},
    )
    if grant_type == "authorization_code":
        result = await database_executor.run(lambda db: service.exchange_authorization_code(
            db, client_id=client_id, client_secret=client_secret, code=required(form, "code"),
            redirect_uri=required(form, "redirect_uri"), code_verifier=form.get("code_verifier", ""),
        ))
        return OAuthTokenResponse.model_validate(result)
    if grant_type == service.DEVICE_CODE_GRANT_TYPE:
        device_result: dict | DeviceCodePollError = await database_executor.run(
            lambda db: service.exchange_device_code(
                db,
                client_id=client_id,
                client_secret=client_secret,
                device_code=required(form, "device_code"),
            )
        )
        if isinstance(device_result, DeviceCodePollError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=device_result.detail
            )
        return OAuthTokenResponse.model_validate(device_result)
    if grant_type == "refresh_token":
        result = await database_executor.run(lambda db: service.refresh_external_token(
            db, client_id=client_id, client_secret=client_secret, refresh_token=required(form, "refresh_token"),
        ))
        return OAuthTokenResponse.model_validate(result)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported_grant_type")


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT, summary="撤销 OAuth Refresh Token")
async def revoke(
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    form = await read_urlencoded_form(request)
    client_id, client_secret = resolve_client_credentials(request, form)
    audit_service.attach_audit_context(
        request.state, action="oauth.token.revoke", resource_type="oauth_client",
        resource_id=client_id, target_summary=f"OAuth Client {client_id}",
    )
    await database_executor.run(lambda db: service.revoke_token(
        db, token=required(form, "token"), client_id=client_id, client_secret=client_secret,
    ))


@router.get("/userinfo", response_model=OAuthUserInfo, summary="获取 OAuth 用户信息")
async def userinfo(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    result = await database_executor.run(
        lambda db: service.get_userinfo_from_token(db, credentials.credentials)
    )
    return OAuthUserInfo.model_validate(result)
