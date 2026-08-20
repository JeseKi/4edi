# -*- coding: utf-8 -*-
"""用户投诉路由：登录后提交投诉。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Security, status
from sqlalchemy.orm import Session

from src.server.auth.dependencies.current_user import (
    AuthenticatedPrincipal,
    get_current_principal,
)
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.database_executor import DatabaseExecutor, get_database_executor

from . import service
from .schemas import ComplaintCreateIn, ComplaintOut

router = APIRouter(prefix="/api/complaint", tags=["商城-投诉"])

_SCOPE = [SCOPE_PROFILE_READ]


def _require_login(
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=_SCOPE
    ),
) -> AuthenticatedPrincipal:
    return current_user


@router.post(
    "",
    summary="提交投诉",
    response_model=ComplaintOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_complaint(
    payload: ComplaintCreateIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db: Session) -> dict:
        post = service.create_complaint(db, current_user.user_id, payload.model_dump())
        return ComplaintOut.model_validate(post).model_dump()

    return await database_executor.run(_create)
