# -*- coding: utf-8 -*-
"""
scope 分类管理路由
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from src.server.audit import service as audit_service
from src.server.auth.dependencies import (
    AuthenticatedPrincipal,
    get_current_admin,
    get_current_admin_writer,
)
from src.server.database_executor import DatabaseExecutor, get_database_executor

from . import service
from .schemas import ManagedScopeOut, ManagedScopeUpdate

router = APIRouter(prefix="/api/admin/scopes", tags=["Scope 管理"])


@router.get(
    "",
    response_model=list[ManagedScopeOut],
    summary="获取 scope 列表",
    description="管理员查看系统内所有已知 scope 及其分类",
    responses={
        200: {"description": "获取成功"},
        403: {"description": "无管理员权限"},
    },
)
async def list_managed_scopes(
    _: AuthenticatedPrincipal = Depends(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [ManagedScopeOut.model_validate(item) for item in service.list_scopes(db)]
    )


@router.patch(
    "/{scope}",
    response_model=ManagedScopeOut,
    summary="更新 scope 分类",
    description="管理员更新指定 scope 的分类，仅支持普通、敏感或危险",
    responses={
        200: {"description": "更新成功"},
        403: {"description": "无管理员权限"},
        404: {"description": "scope 不存在"},
    },
)
async def update_managed_scope(
    request: Request,
    scope: str,
    payload: ManagedScopeUpdate,
    _: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _update(db) -> tuple[ManagedScopeOut, str]:
        before_category = service.get_scope_category(db, scope)
        updated = service.update_scope_category(db, scope, payload.category)
        return ManagedScopeOut.model_validate(updated), before_category.value

    result, before_category = await database_executor.run(_update)
    audit_service.attach_audit_context(
        request.state,
        action="admin.scope.category.update",
        resource_type="scope",
        resource_id=scope,
        target_summary=f"Scope {scope}",
        detail={"before_category": before_category, "after_category": payload.category.value},
    )
    return result
