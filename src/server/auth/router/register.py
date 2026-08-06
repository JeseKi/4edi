# -*- coding: utf-8 -*-
"""Registration and verification code routes."""

from fastapi import Depends, HTTPException, Request, status

from src.server.audit import service as audit_service
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.mail import MailDeliveryExecutor, get_mail_delivery_executor
from .. import service
from ..models import User
from ..schemas import (
    PhoneRegisterWithCode,
    PhoneVerificationCodeRequest,
    UserCreate,
    UserProfile,
    UserRegisterWithCode,
    VerificationCodeRequest,
)
from ..service.sms import normalize_mainland_phone
from .base import router


@router.post(
    "/register",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
    description="使用邮箱验证码创建新用户账户",
    response_description="返回新创建的用户信息",
    responses={
        201: {"description": "用户创建成功"},
        400: {"description": "用户名或邮箱已被注册 / 验证码无效"},
    },
)
async def register_user(
    request: Request,
    user_data: UserRegisterWithCode,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.user.register",
        resource_type="user",
        target_summary=f"用户 {user_data.username}",
        actor_identifier=audit_service.mask_identifier(user_data.email.strip().lower()),
        detail={"registration_method": "email_verification_code"},
    )
    await service.verify_turnstile_token(
        request=request,
        token=user_data.turnstile_token,
        action="auth_register",
    )
    normalized_email = user_data.email.strip().lower()
    if not service.verify_code(normalized_email, user_data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期"
        )

    def _register(db) -> UserProfile:
        db_user = service.get_user_by_username(db, username=user_data.username)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册"
            )
        existing_email = db.query(User).filter(User.email == normalized_email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册"
            )
        user_create = UserCreate(
            username=user_data.username, email=normalized_email, password=user_data.password
        )
        return UserProfile.model_validate(service.create_user(db=db, user_data=user_create))

    new_user = await database_executor.run(_register)
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.user.register",
        user=new_user,
        detail={"registration_method": "email_verification_code"},
    )
    return new_user


@router.post(
    "/send-verification-code",
    summary="发送邮箱验证码",
    responses={
        200: {"description": "验证码发送成功"},
        429: {"description": "发送过于频繁"},
        500: {"description": "验证码发送失败"},
    },
)
async def send_verification_code(
    request: Request,
    payload: VerificationCodeRequest,
    mail_delivery_executor: MailDeliveryExecutor = Depends(get_mail_delivery_executor),
):
    normalized_email = payload.email.strip().lower()
    audit_service.attach_audit_context(
        request.state,
        action="auth.email_verification.request",
        resource_type="auth",
        target_summary="请求邮箱验证码",
        actor_identifier=audit_service.mask_identifier(normalized_email),
    )
    await service.verify_turnstile_token(
        request=request,
        token=payload.turnstile_token,
        action="auth_send_verification_code",
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
    "/register-with-code",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="使用验证码注册用户",
    description="使用邮箱验证码创建新用户账户",
    response_description="返回新创建的用户信息",
    responses={
        201: {"description": "用户创建成功"},
        400: {"description": "用户名或邮箱已被注册 / 验证码无效"},
    },
)
async def register_user_with_code(
    request: Request,
    user_data: UserRegisterWithCode,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state,
        action="auth.user.register",
        resource_type="user",
        target_summary=f"用户 {user_data.username}",
        actor_identifier=audit_service.mask_identifier(user_data.email.strip().lower()),
        detail={"registration_method": "email_verification_code"},
    )
    await service.verify_turnstile_token(
        request=request,
        token=user_data.turnstile_token,
        action="auth_register_with_code",
    )
    normalized_email = user_data.email.strip().lower()
    if not service.verify_code(normalized_email, user_data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期"
        )

    def _register(db) -> UserProfile:
        db_user = service.get_user_by_username(db, username=user_data.username)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册"
            )
        existing_email = db.query(User).filter(User.email == normalized_email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册"
            )
        user_create = UserCreate(
            username=user_data.username, email=normalized_email, password=user_data.password
        )
        return UserProfile.model_validate(service.create_user(db=db, user_data=user_create))

    new_user = await database_executor.run(_register)
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.user.register",
        user=new_user,
        detail={"registration_method": "email_verification_code"},
    )
    return new_user


@router.post(
    "/send-phone-verification-code",
    summary="发送手机验证码",
    responses={
        200: {"description": "验证码发送成功"},
        429: {"description": "发送过于频繁"},
        500: {"description": "验证码发送失败"},
    },
)
async def send_phone_verification_code(
    request: Request,
    payload: PhoneVerificationCodeRequest,
):
    normalized_phone = normalize_mainland_phone(payload.phone)
    audit_service.attach_audit_context(
        request.state,
        action="auth.phone_verification.request",
        resource_type="auth",
        target_summary="请求手机验证码",
        actor_identifier=audit_service.mask_identifier(normalized_phone),
    )
    await service.verify_turnstile_token(
        request=request,
        token=payload.turnstile_token,
        action="auth_send_phone_verification_code",
    )

    try:
        service.send_phone_verification_code(normalized_phone)
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
    "/register-with-phone-code",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="手机号注册用户",
    description="使用手机短信验证码创建新用户账户",
    responses={
        201: {"description": "用户创建成功"},
        400: {"description": "手机号已注册 / 验证码无效"},
    },
)
async def register_user_with_phone_code(
    request: Request,
    user_data: PhoneRegisterWithCode,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    normalized_phone = normalize_mainland_phone(user_data.phone)
    audit_service.attach_audit_context(
        request.state,
        action="auth.user.register",
        resource_type="user",
        target_summary=f"手机号 {audit_service.mask_identifier(normalized_phone)}",
        actor_identifier=audit_service.mask_identifier(normalized_phone),
        detail={"registration_method": "phone_verification_code"},
    )
    await service.verify_turnstile_token(
        request=request,
        token=user_data.turnstile_token,
        action="auth_register_with_phone_code",
    )

    def _register(db) -> UserProfile:
        new_user = service.register_with_phone(
            db, normalized_phone, user_data.password, user_data.code
        )
        return UserProfile.model_validate(new_user)

    new_user = await database_executor.run(_register)
    audit_service.attach_user_audit_context(
        request.state,
        action="auth.user.register",
        user=new_user,
        detail={"registration_method": "phone_verification_code"},
    )
    return new_user
