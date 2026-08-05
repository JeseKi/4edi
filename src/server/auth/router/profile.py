# -*- coding: utf-8 -*-
"""Profile routes."""

from fastapi import Depends, HTTPException, Request, Security, status

from src.server.audit import service as audit_service
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.mail import MailDeliveryExecutor, get_mail_delivery_executor
from .. import service
from ..dao import UserDAO
from ..dependencies import AuthenticatedPrincipal, get_current_principal
from ..models import User
from ..schemas import (
    EmailChangeCodeRequest,
    EmailChangeConfirm,
    UserProfile,
    UserUpdate,
)
from .base import router


@router.get(
    "/profile",
    response_model=UserProfile,
    summary="获取用户资料",
    description="获取当前登录用户的详细信息",
    response_description="返回当前用户的完整资料信息",
    responses={
        200: {"description": "获取用户资料成功"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def get_profile(
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db) -> UserProfile:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        return UserProfile.model_validate(user)

    return await database_executor.run(_get)


@router.put(
    "/profile",
    response_model=UserProfile,
    summary="更新用户资料",
    description="更新当前登录用户的个人信息，包括用户名、姓名等基础资料",
    response_description="返回更新后的用户资料信息",
    responses={
        200: {"description": "用户资料更新成功"},
        400: {"description": "用户名已被注册"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def update_profile(
    request: Request,
    user_data: UserUpdate,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_WRITE]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    update_payload = user_data.model_dump(exclude_unset=True)

    def _update(db) -> tuple[UserProfile, dict]:
        user = UserDAO(db).get_by_id(current_user.user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        before = {"username": user.username, "name": user.name}
        normalized_payload = dict(update_payload)
        if "username" in normalized_payload:
            raw_username = normalized_payload["username"]
            if raw_username is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空")
            normalized_username = raw_username.strip()
            if not normalized_username:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空")
            existing_user = db.query(User).filter(User.username == normalized_username).first()
            if existing_user and existing_user.id != user.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册")
            normalized_payload["username"] = normalized_username
        updated_user = service.update_user(
            db=db, user=user, user_data=UserUpdate(**normalized_payload)
        )
        after = {"username": updated_user.username, "name": updated_user.name}
        changed_fields = [key for key, value in after.items() if before[key] != value]
        detail = {
            "changed_fields": changed_fields,
            "before": {key: before[key] for key in changed_fields},
            "after": {key: after[key] for key in changed_fields},
        }
        return UserProfile.model_validate(updated_user), detail

    updated_user, detail = await database_executor.run(_update)
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.profile.update",
        user=updated_user,
        detail=detail,
    )
    return updated_user


@router.post(
    "/profile/email-change/code",
    summary="发送邮箱修改验证码",
    responses={
        200: {"description": "验证码发送成功"},
        400: {"description": "新邮箱与当前邮箱相同"},
        401: {"description": "未认证或令牌无效"},
        429: {"description": "发送过于频繁"},
        500: {"description": "验证码发送失败"},
    },
)
async def send_email_change_code(
    request: Request,
    payload: EmailChangeCodeRequest,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_EMAIL_WRITE]
    ),
    mail_delivery_executor: MailDeliveryExecutor = Depends(get_mail_delivery_executor),
):
    normalized_email = payload.email.strip().lower()
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.profile.email_change.request",
        user=current_user,
        detail={"new_email": audit_service.mask_identifier(normalized_email)},
    )
    if normalized_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="新邮箱不能与当前邮箱相同"
        )

    try:
        await mail_delivery_executor.run(service.send_verification_code, normalized_email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        )
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="验证码发送失败"
        )

    return {"message": "验证码已发送"}


@router.post(
    "/profile/email-change/confirm",
    response_model=UserProfile,
    summary="确认修改邮箱",
    responses={
        200: {"description": "邮箱修改成功"},
        400: {"description": "验证码无效、邮箱已被使用或与当前邮箱相同"},
        401: {"description": "未认证或令牌无效"},
    },
)
async def confirm_email_change(
    request: Request,
    payload: EmailChangeConfirm,
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_PROFILE_EMAIL_WRITE]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    normalized_email = payload.email.strip().lower()
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.profile.email.update",
        user=current_user,
        detail={"old_email": audit_service.mask_identifier(current_user.email)},
    )
    if normalized_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="新邮箱不能与当前邮箱相同"
        )

    if not service.verify_code(normalized_email, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期"
        )

    def _confirm(db) -> tuple[UserProfile, dict]:
        existing_user = db.query(User).filter(User.email == normalized_email).first()
        if existing_user and existing_user.id != current_user.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被使用")
        db_user = UserDAO(db).get_by_id(current_user.user_id)
        if db_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证或令牌无效")
        old_email = audit_service.mask_identifier(db_user.email)
        db_user.email = normalized_email
        db.flush()
        db.refresh(db_user)
        return UserProfile.model_validate(db_user), {"old_email": old_email}

    db_user, detail = await database_executor.run(_confirm)
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.profile.email.update",
        user=db_user,
        detail={**detail, "new_email": audit_service.mask_identifier(normalized_email)},
    )
    return db_user
