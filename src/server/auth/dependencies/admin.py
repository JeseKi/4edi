# -*- coding: utf-8 -*-
"""管理员认证依赖。"""

from fastapi import Security

from .. import service
from ..schemas import UserRole
from .current_user import AuthenticatedPrincipal, get_current_principal
from .exceptions import insufficient_role_exception


ADMINISTRATIVE_ROLES = frozenset({UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value})


def is_administrative_role(role: str) -> bool:
    return role in ADMINISTRATIVE_ROLES


async def get_current_admin(
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_ADMIN_USERS_READ]
    ),
) -> AuthenticatedPrincipal:
    """
    验证当前用户是否为管理员。

    参数:
        current_user: 已验证的用户对象

    返回:
        User: 管理员用户对象

    异常:
        HTTPException: 当用户非管理员时抛出 403 禁止访问异常
    """
    if not is_administrative_role(current_user.role):
        raise insufficient_role_exception(
            [service.SCOPE_ADMIN_USERS_READ], UserRole.ADMIN.value
        )
    return current_user


async def get_current_admin_writer(
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[service.SCOPE_ADMIN_USERS_WRITE]
    ),
) -> AuthenticatedPrincipal:
    if not is_administrative_role(current_user.role):
        raise insufficient_role_exception(
            [service.SCOPE_ADMIN_USERS_WRITE], UserRole.ADMIN.value
        )
    return current_user
