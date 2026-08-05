# -*- coding: utf-8 -*-
"""Password change routes."""

from fastapi import Depends, HTTPException, Request, Security, status

from src.server.audit import service as audit_service
from src.server.config import global_config
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.mail import MailDeliveryExecutor, get_mail_delivery_executor
from .. import service
from ..dao import UserDAO
from ..dependencies import AuthenticatedPrincipal, get_current_principal
from ..schemas import PasswordChangeConfirm
from .base import router


@router.post(
    "/profile/password-change/link",
    summary="发送密码修改确认链接",
    description="向当前登录用户邮箱发送密码修改确认链接，点击后可在页面中设置新密码",
    responses={
        200: {"description": "确认链接发送成功"},
        401: {"description": "未认证或令牌无效"},
        429: {"description": "发送过于频繁"},
        500: {"description": "确认链接发送失败"},
    },
)
async def send_password_change_link(
    request: Request,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_PASSWORD_WRITE]
    ),
    mail_delivery_executor: MailDeliveryExecutor = Depends(get_mail_delivery_executor),
):
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.password_change.request",
        user=current_user,
        detail={"delivery": "email"},
    )
    try:
        if not global_config.app.domain:
            raise RuntimeError("APP_DOMAIN 未配置")
        await mail_delivery_executor.run(
            service.send_password_change_link,
            user_id=current_user.user_id,
            email=current_user.email,
            app_domain=global_config.app.domain,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="确认链接发送失败",
        )

    return {"message": "确认链接已发送"}


@router.post(
    "/profile/password-change/confirm",
    summary="确认修改密码",
    description="使用邮件中的确认 token 设置新密码",
    responses={
        200: {"description": "密码修改成功"},
        400: {"description": "确认链接无效或已过期"},
        404: {"description": "用户不存在"},
    },
)
async def confirm_password_change(
    request: Request,
    payload: PasswordChangeConfirm,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.password.change.confirm",
        resource_type="user",
        target_summary="通过确认链接修改密码",
    )
    normalized_token = payload.token.strip()
    if len(normalized_token) != 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="确认链接无效或已过期"
        )

    user_id = service.verify_password_change_token(normalized_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="确认链接无效或已过期"
        )

    def _change(db) -> dict:
        user = UserDAO(db).get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="确认链接无效或已过期"
            )
        user.set_password(payload.new_password)
        db.flush()
        return {"id": user.id, "username": user.username}

    user = await database_executor.run(_change)
    audit_service.attach_audit_context(
        request.state,
        action="auth.password.change.confirm",
        resource_type="user",
        resource_id=user["id"],
        target_summary=f"用户 {user['username']} (ID {user['id']})",
        detail={"security_operation": "password_update", "verification_method": "change_link"},
    )
    return {"message": "密码修改成功"}
