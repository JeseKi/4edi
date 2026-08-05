# -*- coding: utf-8 -*-
"""管理员用户管理的请求短事务服务。"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.dao import UserDAO
from src.server.auth.dependencies import AuthenticatedPrincipal
from src.server.auth.models import User
from src.server.auth.schemas import UserRole, UserStatus
from src.server.auth.service import (
    get_role_scopes,
    revoke_all_user_sessions,
    serialize_scopes,
    validate_scope_overrides,
)


def _management_forbidden() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="管理员只能管理普通用户",
    )


def _is_super_admin(principal: AuthenticatedPrincipal) -> bool:
    return principal.role == UserRole.SUPER_ADMIN.value


def assert_can_create_user(
    principal: AuthenticatedPrincipal, role: UserRole
) -> None:
    if not _is_super_admin(principal) and role != UserRole.USER:
        _management_forbidden()


def assert_can_manage_users(
    principal: AuthenticatedPrincipal,
    users: list[User],
    *,
    next_role: UserRole | None = None,
) -> None:
    """校验管理员对一组用户的写入权限，调用方须先处理自身操作限制。"""
    if _is_super_admin(principal):
        return
    if next_role is not None and next_role != UserRole.USER:
        _management_forbidden()
    if any(user.id != principal.user_id and user.role != UserRole.USER for user in users):
        _management_forbidden()


def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    name: str | None = None,
    role: UserRole | None = None,
    status: UserStatus | None = None,
) -> User:
    selected_role = role if role else UserRole.USER
    selected_status = status if status else UserStatus.ACTIVE
    tmp_user = User(
        username=username,
        email=email,
        name=name,
        role=selected_role,
        status=selected_status,
    )
    tmp_user.set_password(password)
    user = UserDAO(db).create(
        tmp_user.username,
        tmp_user.email,
        tmp_user.password_hash,
        role=selected_role,
        status=selected_status,
        scope_overrides=serialize_scopes(get_role_scopes(selected_role)),
    )

    if name is not None:
        user = UserDAO(db).update(user, name=name)
    return user


def list_users(db: Session) -> list[User]:
    return UserDAO(db).list_all()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return UserDAO(db).get_by_id(user_id)


def normalize_user_ids(user_ids: list[int]) -> list[int]:
    normalized_ids: list[int] = []
    seen_ids: set[int] = set()
    for user_id in user_ids:
        if user_id in seen_ids:
            continue
        normalized_ids.append(user_id)
        seen_ids.add(user_id)
    if not normalized_ids:
        raise ValueError("请选择至少一个用户")
    return normalized_ids


def list_users_by_ids(db: Session, user_ids: list[int]) -> list[User]:
    normalized_ids = normalize_user_ids(user_ids)
    users = (
        db.query(User)
        .filter(User.id.in_(normalized_ids), User.deleted_at.is_(None))
        .all()
    )
    users_by_id = {user.id: user for user in users}
    missing_ids = [user_id for user_id in normalized_ids if user_id not in users_by_id]
    if missing_ids:
        raise LookupError("用户不存在")
    return [users_by_id[user_id] for user_id in normalized_ids]


def assert_current_admin_not_in_users(users: list[User], current_admin_id: int) -> None:
    if any(user.id == current_admin_id for user in users):
        raise ValueError("不能批量操作当前登录用户")


def update_user(db: Session, user: User, update_data: dict) -> User:
    should_revoke_sessions = False
    next_role = update_data.get("role")
    if isinstance(next_role, UserRole):
        update_data["scope_overrides"] = serialize_scopes(get_role_scopes(next_role))
        should_revoke_sessions = True

    if "status" in update_data:
        should_revoke_sessions = True

    updated_user = UserDAO(db).update(user, **update_data)
    if should_revoke_sessions:
        updated_user = revoke_all_user_sessions(db, updated_user)
    return updated_user


def bulk_update_users(db: Session, users: list[User], update_data: dict) -> list[User]:
    return [update_user(db, user, dict(update_data)) for user in users]


def update_user_scopes(db: Session, user: User, scopes: list[str]) -> User:
    normalized_scopes = validate_scope_overrides(user.role, scopes)
    updated_user = UserDAO(db).update(
        user,
        scope_overrides=serialize_scopes(normalized_scopes),
    )
    return revoke_all_user_sessions(db, updated_user)


def delete_user(db: Session, user: User) -> None:
    revoke_all_user_sessions(db, user)
    UserDAO(db).soft_delete(user)


def bulk_delete_users(db: Session, users: list[User]) -> None:
    dao = UserDAO(db)
    for user in users:
        revoke_all_user_sessions(db, user)
        dao.soft_delete(user)
