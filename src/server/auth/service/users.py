# -*- coding: utf-8 -*-
"""用户查询与写入相关服务。"""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..dao import UserDAO
from ..models import User
from ..schemas import UserCreate, UserUpdate, UserStatus
from .sms import MAINLAND_PHONE_PATTERN, normalize_mainland_phone


def is_user_disabled(user: User) -> bool:
    return user.deleted_at is not None or user.status == UserStatus.INACTIVE


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return UserDAO(db).get_by_username(username)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return UserDAO(db).get_by_email(email)


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    return UserDAO(db).get_by_phone(phone)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    login_identifier = username.strip()
    user = get_user_by_username(db, login_identifier)
    if not user:
        user = get_user_by_email(db, login_identifier.lower())
    if not user and MAINLAND_PHONE_PATTERN.fullmatch(login_identifier):
        user = get_user_by_phone(db, login_identifier)
    if not user or not user.check_password(password):
        return None
    return user


def create_phone_placeholder_email(phone: str) -> str:
    """为手机号注册用户生成确定性的占位邮箱。"""
    digest = hashlib.sha256(phone.encode("utf-8")).hexdigest()[:32]
    return f"phone_{digest}@phone.mall.site"


def create_unique_random_username(db: Session, prefix: str = "user") -> str:
    """生成不重复的随机用户名。"""
    for _ in range(10):
        candidate = f"{prefix}_{secrets.token_hex(4)}"
        if not get_user_by_username(db, candidate):
            return candidate
    raise RuntimeError("无法生成唯一用户名")


def register_with_phone(
    db: Session, phone: str, password: str, code: str
) -> User:
    """使用手机号验证码注册新用户。"""
    normalized_phone = normalize_mainland_phone(phone)
    from .verification import verify_code

    if not verify_code(normalized_phone, code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期"
        )
    existing_phone = get_user_by_phone(db, normalized_phone)
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该手机号已绑定其他账号"
        )
    username = create_unique_random_username(db)
    placeholder_email = create_phone_placeholder_email(normalized_phone)
    tmp_user = User(username=username, email=placeholder_email)
    tmp_user.set_password(password)
    return UserDAO(db).create(
        tmp_user.username, tmp_user.email, tmp_user.password_hash, phone=normalized_phone
    )


def create_user(db: Session, user_data: UserCreate) -> User:
    # 先构造密码哈希
    tmp_user = User(username=user_data.username, email=user_data.email)
    tmp_user.set_password(user_data.password)
    return UserDAO(db).create(tmp_user.username, tmp_user.email, tmp_user.password_hash)


def update_user(db: Session, user: User, user_data: UserUpdate) -> User:
    update_data = user_data.model_dump(exclude_unset=True)
    return UserDAO(db).update(user, **update_data)
