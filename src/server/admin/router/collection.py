# -*- coding: utf-8 -*-
"""管理员用户集合路由。"""

from fastapi import Depends, HTTPException, Request, status

from src.server.audit import service as audit_service
from src.server.auth.dependencies import (
    AuthenticatedPrincipal,
    get_current_admin,
    get_current_admin_writer,
)
from src.server.auth.models import User
from src.server.database_executor import DatabaseExecutor, get_database_executor

from .. import service
from ..schemas import AdminUserBulkDelete, AdminUserBulkUpdate, AdminUserCreate, AdminUserOut
from . import router
from .helpers import changed_values, user_snapshot


@router.get("/users", response_model=list[AdminUserOut], summary="获取用户列表")
async def list_users(
    _: AuthenticatedPrincipal = Depends(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [AdminUserOut.model_validate(user) for user in service.list_users(db)]
    )


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED, summary="创建用户")
async def create_user(
    request: Request,
    payload: AdminUserCreate,
    current_admin: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="admin.user.create", resource_type="user",
        target_summary=f"用户 {payload.username}",
        detail={"role": payload.role.value, "status": payload.status.value},
    )
    def _create(db) -> tuple[AdminUserOut, dict]:
        service.assert_can_create_user(current_admin, payload.role)
        if db.query(User).filter(User.username == payload.username).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册")
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被使用")
        user = service.create_user(
            db, username=payload.username, email=payload.email, password=payload.password,
            name=payload.name, role=payload.role, status=payload.status,
        )
        return AdminUserOut.model_validate(user), user_snapshot(user)

    user, snapshot = await database_executor.run(_create)
    audit_service.attach_user_audit_context(
        request.state, action="admin.user.create", user=user,
        detail={"created": snapshot},
    )
    return user


@router.patch("/users/bulk", response_model=list[AdminUserOut], summary="批量更新用户")
async def bulk_update_users(
    request: Request,
    payload: AdminUserBulkUpdate,
    current_admin: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="admin.user.bulk_update", resource_type="user",
        target_summary=f"批量更新 {len(set(payload.user_ids))} 个用户",
        detail={"target_user_ids": sorted(set(payload.user_ids))},
    )
    try:
        def _update(db) -> tuple[list[AdminUserOut], dict[str, dict]]:
            users = service.list_users_by_ids(db, payload.user_ids)
            service.assert_current_admin_not_in_users(users, current_admin.user_id)
            service.assert_can_manage_users(
                current_admin, users, next_role=payload.role
            )
            before = {user.id: user_snapshot(user) for user in users}
            update_data = payload.model_dump(exclude={"user_ids"}, exclude_none=True)
            updated_users = service.bulk_update_users(db, users, update_data)
            changes = {
                str(user.id): changed_values(before[user.id], user_snapshot(user))
                for user in updated_users
            }
            return [AdminUserOut.model_validate(user) for user in updated_users], changes

        updated_users, changes = await database_executor.run(_update)
        audit_service.attach_audit_context(request.state, detail={"changes": changes})
        return updated_users
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/users/bulk", status_code=status.HTTP_204_NO_CONTENT, summary="批量删除用户")
async def bulk_delete_users(
    request: Request,
    payload: AdminUserBulkDelete,
    current_admin: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="admin.user.bulk_delete", resource_type="user",
        target_summary=f"批量删除 {len(set(payload.user_ids))} 个用户",
        detail={"target_user_ids": sorted(set(payload.user_ids))},
    )
    try:
        def _delete(db) -> list[dict]:
            users = service.list_users_by_ids(db, payload.user_ids)
            service.assert_current_admin_not_in_users(users, current_admin.user_id)
            service.assert_can_manage_users(current_admin, users)
            deleted_users = [user_snapshot(user) | {"id": user.id} for user in users]
            service.bulk_delete_users(db, users)
            for user, snapshot in zip(users, deleted_users, strict=True):
                snapshot["soft_deleted_at"] = user.deleted_at.isoformat() if user.deleted_at else None
            return deleted_users

        deleted_users = await database_executor.run(_delete)
        audit_service.attach_audit_context(request.state, detail={"deleted_users": deleted_users})
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
