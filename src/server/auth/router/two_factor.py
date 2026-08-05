# -*- coding: utf-8 -*-
"""2FA routes."""

from fastapi import Depends, HTTPException, Request, Response, Security, status

from src.server.audit import service as audit_service
from src.server.database_executor import DatabaseExecutor, get_database_executor
from .. import service
from ..config import auth_config
from ..dao import UserDAO
from ..dependencies import AuthenticatedPrincipal, get_current_principal
from ..models import User
from ..schemas import (
    BackupCodesResponse,
    MessageResponse,
    TokenResponse,
    TwoFactorBackupCodesRegenerateRequest,
    TwoFactorDisableRequest,
    TwoFactorSetupConfirmRequest,
    TwoFactorSetupStartResponse,
    TwoFactorVerifyRequest,
)
from .base import router


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


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=auth_config.refresh_cookie_name,
        path="/api/auth",
        secure=auth_config.refresh_cookie_secure,
        samesite=auth_config.refresh_cookie_samesite,  # type: ignore[arg-type]
    )


def _build_token_response(access_token: str, user: User) -> dict[str, str]:
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "scope": service.serialize_scopes(service.get_user_scopes(user)),
    }


@router.post(
    "/2fa/verify",
    response_model=TokenResponse,
    summary="完成登录阶段 2FA 验证",
    responses={
        200: {"description": "2FA 验证成功"},
        400: {"description": "验证码错误"},
        401: {"description": "挑战无效、过期或已耗尽"},
    },
)
async def verify_login_two_factor(
    request: Request,
    payload: TwoFactorVerifyRequest,
    response: Response,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.2fa.verify_login",
        resource_type="auth",
        target_summary="完成登录二步验证",
    )
    def _verify(
        db,
    ) -> tuple[
        dict[str, str], dict[str, str | int] | None, tuple[int, str] | None
    ]:
        try:
            challenge = service.get_valid_login_challenge(db, payload.challenge_token)
        except service.LoginChallengeError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
        user = UserDAO(db).get_by_id(challenge.user_id)
        if user is None or not service.is_two_factor_enabled(user):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登录挑战无效或已过期",
            )
        verified_with = service.verify_user_two_factor_code(db, user, payload.code)
        if verified_with is None:
            challenge = service.record_login_challenge_failure(db, challenge)
            if challenge.attempt_count >= auth_config.two_factor_max_verify_attempts:
                return {}, None, (
                    status.HTTP_401_UNAUTHORIZED,
                    "验证码错误次数过多，请重新登录",
                )
            return {}, None, (status.HTTP_400_BAD_REQUEST, "验证码或 backup code 错误")
        service.consume_login_challenge(db, challenge)
        access_token, refresh_token = service.issue_token_pair(db, user)
        return (
            _build_token_response(access_token, user) | {"refresh_token": refresh_token},
            {
                "id": user.id,
                "username": user.username,
                "role": user.role.value,
            },
            None,
        )

    token_data, user, verification_error = await database_executor.run(_verify)
    if verification_error is not None:
        status_code, detail = verification_error
        raise HTTPException(status_code=status_code, detail=detail)
    assert user is not None
    request.state.actor_identifier = user["username"]
    request.state.user_id = user["id"]
    request.state.username = user["username"]
    request.state.user_role = user["role"]
    refresh_token = token_data.pop("refresh_token")
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse.model_validate(token_data)


@router.post(
    "/2fa/setup/start",
    response_model=TwoFactorSetupStartResponse,
    summary="开始 2FA 绑定",
    responses={
        200: {"description": "返回待确认 secret 和 setup token"},
        400: {"description": "当前用户已经启用 2FA"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def start_two_factor_setup(
    request: Request,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_WRITE]
    ),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.2fa.setup_start",
        resource_type="auth",
        target_summary="开始绑定二步验证",
    )
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="当前账号已开启 2FA"
        )

    secret = service.generate_totp_secret()
    encrypted_secret = service.encrypt_totp_secret(secret)
    return TwoFactorSetupStartResponse(
        secret=secret,
        secret_masked=service.mask_totp_secret(secret),
        otpauth_url=service.build_otpauth_uri(secret, current_user.email),
        setup_token=service.create_two_factor_setup_token(
            current_user.user_id, encrypted_secret
        ),
    )


@router.post(
    "/2fa/setup/confirm",
    response_model=BackupCodesResponse,
    summary="确认并开启 2FA",
    responses={
        200: {"description": "2FA 开启成功并返回 backup codes"},
        400: {"description": "setup token 或验证码无效"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def confirm_two_factor_setup(
    request: Request,
    payload: TwoFactorSetupConfirmRequest,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_WRITE]
    ),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.2fa.setup_confirm",
        resource_type="auth",
        target_summary="开启二步验证",
    )
    def _confirm(db) -> list[str]:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        if service.is_two_factor_enabled(user):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前账号已开启 2FA")
        try:
            encrypted_secret = service.assert_setup_code_valid(
                payload.setup_token, user, payload.code
            )
        except service.TwoFactorError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        _, backup_codes = service.enable_two_factor(db, user, encrypted_secret)
        return backup_codes

    backup_codes = await database_executor.run(_confirm)
    return BackupCodesResponse(
        backup_codes=backup_codes,
        message="2FA 已开启，请妥善保管 backup codes",
    )


@router.post(
    "/2fa/disable",
    response_model=MessageResponse,
    summary="关闭 2FA",
    responses={
        200: {"description": "2FA 已关闭"},
        400: {"description": "密码或验证码错误"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def disable_two_factor(
    request: Request,
    payload: TwoFactorDisableRequest,
    response: Response,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_WRITE]
    ),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.2fa.disable",
        resource_type="auth",
        target_summary="关闭二步验证",
    )
    def _disable(db) -> None:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        try:
            service.assert_two_factor_can_be_managed(user)
            service.assert_password_verified(user, payload.password)
            service.assert_valid_two_factor_code(db, user, payload.code)
        except service.TwoFactorError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        service.disable_two_factor(db, user)
        service.revoke_all_user_sessions(db, user)

    await database_executor.run(_disable)
    _clear_refresh_cookie(response)
    return {"message": "2FA 已关闭，请重新登录"}


@router.post(
    "/2fa/backup-codes/regenerate",
    response_model=BackupCodesResponse,
    summary="重新生成 backup codes",
    responses={
        200: {"description": "backup codes 已重新生成"},
        400: {"description": "密码或验证码错误"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def regenerate_backup_codes(
    request: Request,
    payload: TwoFactorBackupCodesRegenerateRequest,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_WRITE]
    ),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.2fa.backup_codes_regenerate",
        resource_type="auth",
        target_summary="重新生成二步验证备用码",
    )
    def _regenerate(db) -> list[str]:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        try:
            service.assert_two_factor_can_be_managed(user)
            service.assert_password_verified(user, payload.password)
            service.assert_valid_two_factor_code(db, user, payload.code)
        except service.TwoFactorError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        return service.replace_backup_codes(db, user)

    backup_codes = await database_executor.run(_regenerate)
    return BackupCodesResponse(
        backup_codes=backup_codes,
        message="backup codes 已重新生成",
    )
