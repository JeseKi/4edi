# -*- coding: utf-8 -*-
"""Password reset routes."""

from fastapi import Depends, HTTPException, Request, status

from src.server.audit import service as audit_service
from src.server.config import global_config
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.mail import MailDeliveryExecutor, get_mail_delivery_executor
from .. import service
from ..dao import UserDAO
from ..schemas import PasswordResetLinkRequest, PasswordResetWithToken
from .base import router


@router.post(
    "/forgot-password/link",
    summary="发送密码重置链接",
    responses={
        200: {"description": "重置链接发送成功"},
        404: {"description": "邮箱不存在"},
        429: {"description": "发送过于频繁"},
        500: {"description": "重置链接发送失败"},
    },
)
async def send_password_reset_link(
    request: Request,
    payload: PasswordResetLinkRequest,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    mail_delivery_executor: MailDeliveryExecutor = Depends(get_mail_delivery_executor),
):
    normalized_email = payload.email.strip().lower()
    audit_service.attach_audit_context(
        request.state,
        action="auth.password_reset.request",
        resource_type="auth",
        target_summary="请求密码重置",
        actor_identifier=audit_service.mask_identifier(normalized_email),
    )
    await service.verify_turnstile_token(
        request=request,
        token=payload.turnstile_token,
        action="auth_forgot_password_link",
    )
    existing_user = await database_executor.run(
        lambda db: _password_reset_user_snapshot(db, normalized_email)
    )
    if not existing_user:
        return {"message": "重置链接已发送"}

    audit_service.attach_audit_context(
        request.state,
        action="auth.password_reset.request",
        resource_type="user",
        resource_id=existing_user["id"],
        target_summary=f"用户 {existing_user['username']} (ID {existing_user['id']})",
        detail={"delivery": "email"},
    )

    try:
        if not global_config.app.domain:
            raise RuntimeError("APP_DOMAIN 未配置")
        await mail_delivery_executor.run(
            service.send_password_reset_link, normalized_email, global_config.app.domain
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重置链接发送失败",
        )
    return {"message": "重置链接已发送"}


@router.post(
    "/forgot-password/reset",
    summary="重置密码",
    responses={
        200: {"description": "密码重置成功"},
        400: {"description": "重置链接无效或已过期"},
        404: {"description": "邮箱不存在"},
    },
)
async def reset_password(
    request: Request,
    payload: PasswordResetWithToken,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.password.reset",
        resource_type="user",
        target_summary="通过重置链接修改密码",
    )
    normalized_token = payload.token.strip()
    if len(normalized_token) != 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期"
        )

    email = service.verify_password_reset_token(normalized_token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期"
        )

    def _reset(db) -> dict:
        user = UserDAO(db).get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="重置链接无效或已过期"
            )
        user.set_password(payload.new_password)
        db.flush()
        return {"id": user.id, "username": user.username}

    user = await database_executor.run(_reset)
    audit_service.attach_audit_context(
        request.state,
        action="auth.password.reset",
        resource_type="user",
        resource_id=user["id"],
        target_summary=f"用户 {user['username']} (ID {user['id']})",
        detail={"security_operation": "password_update", "verification_method": "reset_link"},
    )
    return {"message": "密码重置成功"}


def _password_reset_user_snapshot(db, email: str) -> dict[str, int | str] | None:
    user = UserDAO(db).get_by_email(email)
    if user is None:
        return None
    return {"id": user.id, "username": user.username}
