# -*- coding: utf-8 -*-
"""当前用户认证依赖。"""

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import SecurityScopes
from jose import JWTError
from sqlalchemy.orm import Session

from src.server.config import global_config
from src.server.database_executor import DatabaseExecutor, get_database_executor

from .. import service
from ..config import auth_config
from ..dao import UserDAO
from ..models import User
from .exceptions import credentials_exception
from .security import oauth2_scheme
from .validators import (
    decode_token,
    validate_dangerous_scope_two_factor,
    validate_scopes,
    validate_token_type,
    validate_token_version,
    validate_user_scopes,
)


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """离开数据库 Session 后仍可安全使用的认证身份快照。"""

    user_id: int
    username: str
    role: str
    email: str
    two_factor_enabled: bool


async def get_current_user(
    security_scopes: SecurityScopes,
    request: Request,
    token: str = Depends(oauth2_scheme),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
) -> AuthenticatedPrincipal:
    """兼容旧依赖名，但只返回可安全离开事务的认证快照。"""
    return await _resolve_current_principal(
        security_scopes, request, token, database_executor
    )


async def get_current_principal(
    security_scopes: SecurityScopes,
    request: Request,
    token: str = Depends(oauth2_scheme),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
) -> AuthenticatedPrincipal:
    """在独立短事务中完成鉴权，避免请求生命周期持有 ORM Session。"""

    return await _resolve_current_principal(
        security_scopes, request, token, database_executor
    )


async def _resolve_current_principal(
    security_scopes: SecurityScopes,
    request: Request,
    token: str,
    database_executor: DatabaseExecutor,
) -> AuthenticatedPrincipal:
    principal = await database_executor.run(
        lambda db: _snapshot_current_user(security_scopes, request, token, db)
    )
    request.state.user_id = principal.user_id
    request.state.username = principal.username
    request.state.user_role = principal.role
    return principal


def _snapshot_current_user(
    security_scopes: SecurityScopes, request: Request, token: str, db: Session
) -> AuthenticatedPrincipal:
    user = _resolve_current_user(security_scopes, request, token, db)
    return AuthenticatedPrincipal(
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        email=user.email,
        two_factor_enabled=service.is_two_factor_enabled(user),
    )


def _resolve_current_user(
    security_scopes: SecurityScopes, request: Request, token: str, db: Session
) -> User:
    auth_exception = credentials_exception(security_scopes.scopes)

    # 开发和测试环境下的特殊处理
    if global_config.app.env in ["dev", "test"] and token == auth_config.test_token:
        user = UserDAO(db).get_by_id(1)
        if user:
            validate_user_scopes(user, security_scopes.scopes)
            validate_dangerous_scope_two_factor(
                request, db, user, security_scopes.scopes
            )
            return user
        raise auth_exception

    try:
        payload = decode_token(token)
        username = validate_token_type(payload, service.TOKEN_TYPE_ACCESS)
        validate_scopes(payload, security_scopes.scopes)
    except JWTError:
        raise auth_exception

    user = service.get_user_by_username(db, username=username)
    if user is None:
        raise auth_exception
    if service.is_user_disabled(user):
        raise credentials_exception()
    validate_token_version(payload, user)
    validate_dangerous_scope_two_factor(request, db, user, security_scopes.scopes)
    return user


def _write_request_identity(request: Request, user: User) -> None:
    request.state.user_id = user.id
    request.state.username = user.username
    request.state.user_role = user.role.value
