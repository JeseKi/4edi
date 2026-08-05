# -*- coding: utf-8 -*-
"""Audit event admin routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Security

from src.server.auth.dependencies import AuthenticatedPrincipal, get_current_principal
from src.server.auth.service.scopes import SCOPE_ADMIN_AUDIT_READ
from src.server.database_executor import DatabaseExecutor, get_database_executor

from . import service
from .schemas import AuditEventListOut

router = APIRouter(prefix="/api/admin/audit-events", tags=["审计日志"])


@router.get(
    "",
    response_model=AuditEventListOut,
    summary="查询审计日志",
    description="管理员分页查询系统写操作和长线任务审计日志。",
)
async def list_audit_events(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: str | None = Query(default=None, max_length=120),
    outcome: Literal["success", "failure"] | None = None,
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] | None = None,
    actor_user_id: int | None = Query(default=None, ge=1),
    resource_type: str | None = Query(default=None, max_length=80),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    _: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_ADMIN_AUDIT_READ]
    ),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db) -> AuditEventListOut:
        items, total = service.list_events(
            db,
            page=page,
            page_size=page_size,
            q=q,
            outcome=outcome,
            method=method,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            created_from=created_from,
            created_to=created_to,
        )
        return AuditEventListOut(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    return await database_executor.run(_list)
