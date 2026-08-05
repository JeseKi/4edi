"""Login and token refresh routes."""

from fastapi.responses import JSONResponse

from fastapi import Depends, HTTPException, Request, Response, Security, status
from jose import jwt

from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.audit import service as audit_service
from .. import service
from ..config import auth_config
from ..dao import RefreshTokenDAO, UserDAO
from ..dependencies import (
    AuthenticatedPrincipal,
    CurrentRefreshSession,
    get_current_refresh_session,
    get_current_principal,
)
from ..models import User
from ..schemas import LoginChallengeResponse, MessageResponse, TokenResponse, UserLogin
from .base import router


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=auth_config.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=auth_config.refresh_cookie_secure,
        samesite=auth_config.refresh_cookie_samesite,  # type: ignore
        max_age=auth_config.refresh_token_ttl_days * 24 * 60 * 60,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=auth_config.refresh_cookie_name,
        path="/api/auth",
        secure=auth_config.refresh_cookie_secure,
        samesite=auth_config.refresh_cookie_samesite,  # type: ignore
    )


def _build_token_response(access_token: str, user: User) -> dict[str, str]:
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "scope": service.serialize_scopes(service.get_user_scopes(user)),
    }


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description="用户通过用户名或邮箱以及密码进行身份验证，获取访问令牌和刷新令牌",
    response_description="返回访问令牌和刷新令牌",
    responses={
        200: {"description": "登录成功"},
        202: {"model": LoginChallengeResponse, "description": "需要继续完成 2FA"},
        401: {"description": "用户名/邮箱或密码错误"},
    },
)
async def login_for_access_token(
    request: Request,
    login_data: UserLogin,
    response: Response,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.login",
        resource_type="auth",
        target_summary="用户登录",
        actor_identifier=login_data.username,
    )
    await service.verify_turnstile_token(
        request=request,
        token=login_data.turnstile_token,
        action="auth_login",
    )
    def _login(db) -> tuple[str, dict]:
        user = service.authenticate_user(db, login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="不正确的用户名/邮箱或密码",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if service.is_user_disabled(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已被停用")
        identity = {"id": user.id, "username": user.username, "role": user.role.value}
        if service.is_two_factor_enabled(user):
            return "challenge", {"challenge_token": service.begin_login_challenge(db, user), **identity}
        access_token, refresh_token = service.issue_token_pair(db, user)
        return "token", {**_build_token_response(access_token, user), "refresh_token": refresh_token, **identity}

    result_type, result = await database_executor.run(_login)
    request.state.user_id = result["id"]
    request.state.username = result["username"]
    request.state.user_role = result["role"]
    if result_type == "challenge":
        payload = LoginChallengeResponse(challenge_token=result["challenge_token"])
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED, content=payload.model_dump()
        )

    _set_refresh_cookie(response, result.pop("refresh_token"))
    return TokenResponse.model_validate(result)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="刷新访问令牌",
    description="使用刷新令牌获取新的访问令牌和刷新令牌对",
    response_description="返回新的访问令牌和刷新令牌",
    responses={
        200: {"description": "令牌刷新成功"},
        401: {"description": "无效的刷新令牌"},
    },
)
async def refresh_access_token(
    request: Request,
    response: Response,
    current_session: CurrentRefreshSession = Depends(get_current_refresh_session),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.refresh",
        resource_type="auth",
        target_summary="刷新访问令牌",
    )
    def _refresh(db) -> tuple[dict[str, str], str]:
        user = UserDAO(db).get_by_id(current_session.user_id)
        refresh_session = RefreshTokenDAO(db).get_active_by_jti(current_session.refresh_jti)
        if user is None or refresh_session is None or refresh_session.user_id != current_session.user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        new_access_token, new_refresh_token = service.rotate_refresh_token(db, user, refresh_session)
        return _build_token_response(new_access_token, user), new_refresh_token

    token_response, new_refresh_token = await database_executor.run(_refresh)
    _set_refresh_cookie(response, new_refresh_token)
    return TokenResponse.model_validate(token_response)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="退出当前设备",
    description="撤销当前设备的 refresh token，并清理认证 cookie",
    response_description="返回退出结果",
    responses={200: {"description": "退出成功"}},
)
async def logout_current_device(
    request: Request,
    response: Response,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.logout",
        resource_type="auth",
        target_summary="退出当前设备",
    )
    refresh_token = request.cookies.get(auth_config.refresh_cookie_name)
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token,
                auth_config.jwt_secret_key,
                algorithms=[auth_config.jwt_algorithm],
            )
            username = payload.get("sub")
            if isinstance(username, str) and username:
                request.state.actor_identifier = username
            refresh_jti = payload.get("jti")
            if isinstance(refresh_jti, str) and refresh_jti:
                await database_executor.run(
                    lambda db: service.revoke_refresh_token(db, refresh_jti)
                )
        except Exception:
            pass

    _clear_refresh_cookie(response)
    return {"message": "已退出当前设备"}


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="退出所有设备",
    description="撤销当前用户的全部会话，并使所有旧 token 立即失效",
    response_description="返回退出结果",
    responses={
        200: {"description": "已退出所有设备"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def logout_all_devices(
    request: Request,
    response: Response,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.logout_all",
        resource_type="auth",
        target_summary="退出所有设备",
    )
    def _logout_all(db) -> None:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        service.revoke_all_user_sessions(db, user)

    await database_executor.run(_logout_all)
    _clear_refresh_cookie(response)
    return {"message": "已退出所有设备"}
