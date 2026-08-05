# -*- coding: utf-8 -*-
"""OAuth routes."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from src.server.auth import service as auth_service
from src.server.auth.config import auth_config
from src.server.auth.dao import UserDAO
from src.server.auth.models import User
from src.server.audit import service as audit_service
from src.server.auth.schemas import LoginChallengeResponse, TokenResponse
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.config import global_config
from src.server.providers import (
    get_github_oauth_provider,
    get_google_oauth_provider,
)
from .dao import OAuthAccountDAO
from .schemas import OAuthProvidersResponse, OAuthTicketExchange
from .service import core
from .service.github import GITHUB_PROVIDER, GitHubOAuthError
from .service.google import GOOGLE_PROVIDER, GoogleOAuthError

router = APIRouter(prefix="/api/oauth", tags=["OAuth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=auth_config.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=auth_config.refresh_cookie_secure,
        samesite=auth_config.refresh_cookie_samesite,  # type: ignore[arg-type]
        max_age=auth_config.refresh_token_ttl_days * 24 * 60 * 60,
        path="/api/auth",
    )


def _build_token_response(access_token: str, user: User) -> dict[str, str]:
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "scope": auth_service.serialize_scopes(auth_service.get_user_scopes(user)),
    }


def _build_frontend_login_url(
    *,
    ticket: str | None = None,
    error: str | None = None,
    redirect_path: str | None = None,
) -> str:
    base_url = global_config.app.domain.strip() or ""
    target = f"{base_url}/login"
    params = {}
    if ticket:
        params["oauth_ticket"] = ticket
    if error:
        params["oauth_error"] = error
    if redirect_path and redirect_path.startswith("/") and not redirect_path.startswith("//"):
        params["oauth_redirect_path"] = redirect_path
    if not params:
        return target
    return f"{target}?{urlencode(params)}"


@router.get(
    "/providers",
    response_model=OAuthProvidersResponse,
    summary="获取已启用 OAuth 渠道",
)
async def list_providers():
    return OAuthProvidersResponse(providers=core.list_enabled_providers())


@router.get(
    "/github/authorize",
    summary="开始 GitHub OAuth 登录",
)
async def authorize_github(
    redirect_path: str | None = Query(default=None),
):
    core.assert_provider_enabled(GITHUB_PROVIDER)
    state = core.create_oauth_state(redirect_path)
    try:
        return RedirectResponse(get_github_oauth_provider().build_authorize_url(state))
    except GitHubOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/github/callback",
    summary="GitHub OAuth 回调",
)
async def github_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    core.assert_provider_enabled(GITHUB_PROVIDER)
    if error:
        return RedirectResponse(_build_frontend_login_url(error=error_description or error))
    if not code or not state:
        return RedirectResponse(_build_frontend_login_url(error="GitHub OAuth 参数缺失"))

    try:
        state_payload = core.decode_oauth_state(state)
    except core.OAuthError as exc:
        return RedirectResponse(_build_frontend_login_url(error=str(exc)))

    try:
        github_user = await get_github_oauth_provider().fetch_user_info(code)
    except (GitHubOAuthError, Exception) as exc:
        return RedirectResponse(_build_frontend_login_url(error=str(exc)))

    def _complete_callback(db) -> str:
        account = OAuthAccountDAO(db).get_by_provider_user_id(
            GITHUB_PROVIDER, github_user.provider_user_id
        )
        existing_user = UserDAO(db).get_by_email(github_user.email)
        user = core.resolve_github_user(db, github_user)
        ticket = core.create_login_ticket(db, GITHUB_PROVIDER, user)
        callback_action = (
            "auth.oauth.login"
            if account is not None
            else ("auth.user.create.via_oauth" if existing_user is None else "auth.oauth.account.link")
        )
        audit_service.create_request_event(
            db,
            request,
            outcome="success",
            action=callback_action,
            resource_type="user",
            resource_id=user.id,
            target_summary=f"用户 {user.username} (ID {user.id})",
            detail={
                "provider": GITHUB_PROVIDER,
                "user_created": existing_user is None,
                "oauth_account_linked": account is None,
                "login_ticket_issued": True,
            },
        )
        return ticket

    try:
        ticket = await database_executor.run(_complete_callback)
    except core.OAuthError as exc:
        return RedirectResponse(_build_frontend_login_url(error=str(exc)))

    redirect_path = state_payload.get("redirect_path")
    return RedirectResponse(
        _build_frontend_login_url(
            ticket=ticket,
            redirect_path=redirect_path if isinstance(redirect_path, str) else None,
        )
    )


@router.get(
    "/google/authorize",
    summary="开始 Google OAuth 登录",
)
async def authorize_google(
    redirect_path: str | None = Query(default=None),
):
    core.assert_provider_enabled(GOOGLE_PROVIDER)
    state = core.create_oauth_state(redirect_path)
    try:
        return RedirectResponse(get_google_oauth_provider().build_authorize_url(state))
    except GoogleOAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/google/callback",
    summary="Google OAuth 回调",
)
async def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    core.assert_provider_enabled(GOOGLE_PROVIDER)
    if error:
        return RedirectResponse(_build_frontend_login_url(error=error_description or error))
    if not code or not state:
        return RedirectResponse(_build_frontend_login_url(error="Google OAuth 参数缺失"))

    try:
        state_payload = core.decode_oauth_state(state)
    except core.OAuthError as exc:
        return RedirectResponse(_build_frontend_login_url(error=str(exc)))

    try:
        google_user = await get_google_oauth_provider().fetch_user_info(code)
    except (GoogleOAuthError, Exception) as exc:
        return RedirectResponse(_build_frontend_login_url(error=str(exc)))

    def _complete_callback(db) -> str:
        account = OAuthAccountDAO(db).get_by_provider_user_id(
            GOOGLE_PROVIDER, google_user.provider_user_id
        )
        existing_user = UserDAO(db).get_by_email(google_user.email)
        user = core.resolve_google_user(db, google_user)
        ticket = core.create_login_ticket(db, GOOGLE_PROVIDER, user)
        callback_action = (
            "auth.oauth.login"
            if account is not None
            else ("auth.user.create.via_oauth" if existing_user is None else "auth.oauth.account.link")
        )
        audit_service.create_request_event(
            db,
            request,
            outcome="success",
            action=callback_action,
            resource_type="user",
            resource_id=user.id,
            target_summary=f"用户 {user.username} (ID {user.id})",
            detail={
                "provider": GOOGLE_PROVIDER,
                "user_created": existing_user is None,
                "oauth_account_linked": account is None,
                "login_ticket_issued": True,
            },
        )
        return ticket

    try:
        ticket = await database_executor.run(_complete_callback)
    except core.OAuthError as exc:
        return RedirectResponse(_build_frontend_login_url(error=str(exc)))

    redirect_path = state_payload.get("redirect_path")
    return RedirectResponse(
        _build_frontend_login_url(
            ticket=ticket,
            redirect_path=redirect_path if isinstance(redirect_path, str) else None,
        )
    )


@router.post(
    "/ticket",
    response_model=TokenResponse | LoginChallengeResponse,
    summary="交换 OAuth 登录票据",
    responses={
        200: {"description": "OAuth 登录成功或需要继续完成 2FA"},
        401: {"description": "票据无效、过期或已消费"},
    },
)
async def exchange_ticket(
    request: Request,
    payload: OAuthTicketExchange,
    response: Response,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.oauth.ticket.exchange",
        resource_type="auth",
        target_summary="交换 OAuth 登录票据",
    )

    def _exchange(db) -> tuple[dict[str, str], dict[str, int | str]]:
        user, challenge_token = core.exchange_login_ticket(db, payload.ticket)
        user_snapshot: dict[str, int | str] = {
            "id": user.id,
            "username": user.username,
            "role": user.role.value,
        }
        if challenge_token:
            challenge_result: dict[str, str] = {"challenge_token": challenge_token}
            return challenge_result, user_snapshot
        access_token, refresh_token = auth_service.issue_token_pair(db, user)
        token_result = _build_token_response(access_token, user)
        token_result["refresh_token"] = refresh_token
        return token_result, user_snapshot

    result, user = await database_executor.run(_exchange)
    audit_service.attach_audit_context(
        request.state,
        action="auth.oauth.ticket.exchange",
        resource_type="user",
        resource_id=user["id"],
        target_summary=f"用户 {user['username']} (ID {user['id']})",
        detail={"two_factor_required": "challenge_token" in result},
    )
    if "challenge_token" in result:
        return LoginChallengeResponse(challenge_token=result["challenge_token"])

    _set_refresh_cookie(response, result.pop("refresh_token"))
    return TokenResponse.model_validate(result)
