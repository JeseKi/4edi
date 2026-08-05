# -*- coding: utf-8 -*-
"""管理员单个用户路由。"""

from fastapi import Depends, HTTPException, Request, status

from src.server.audit import service as audit_service
from src.server.auth.dependencies import AuthenticatedPrincipal, get_current_admin_writer
from src.server.auth.models import User
from src.server.database_executor import DatabaseExecutor, get_database_executor

from .. import service
from ..schemas import AdminUserOut, AdminUserScopesUpdate, AdminUserUpdate
from . import router
from .helpers import changed_values, user_snapshot


def _attach_target(request: Request, action: str, user_id: int) -> None:
    audit_service.attach_audit_context(
        request.state, action=action, resource_type="user", resource_id=user_id,
        target_summary=f"用户 ID {user_id}",
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut, summary="更新用户信息")
async def update_user(
    request: Request,
    user_id: int,
    payload: AdminUserUpdate,
    current_admin: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    _attach_target(request, "admin.user.update", user_id)

    def _update(db) -> tuple[AdminUserOut, dict]:
        user = service.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        update_data = payload.model_dump(exclude_unset=True)
        if "username" in update_data and update_data["username"] is not None:
            username = update_data["username"].strip()
            if not username:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名不能为空")
            existing = db.query(User).filter(User.username == username).first()
            if existing and existing.id != user.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已被注册")
            update_data["username"] = username
        if "email" in update_data and update_data["email"] is not None:
            email = update_data["email"].strip().lower()
            existing = db.query(User).filter(User.email == email).first()
            if existing and existing.id != user.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被使用")
            update_data["email"] = email
        if user.id == current_admin.user_id:
            if "role" in update_data and update_data["role"] != user.role:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的角色")
            if "status" in update_data and update_data["status"] != user.status:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的状态")
        service.assert_can_manage_users(
            current_admin, [user], next_role=update_data.get("role")
        )
        before = user_snapshot(user)
        password = update_data.pop("password", None)
        if password:
            user.set_password(password)
            db.flush()
            db.refresh(user)
        if update_data:
            user = service.update_user(db, user, update_data)
        detail = changed_values(before, user_snapshot(user))
        if password:
            detail["security_operation"] = "password_update"
        return AdminUserOut.model_validate(user), detail

    user, detail = await database_executor.run(_update)
    audit_service.attach_user_audit_context(request.state, action="admin.user.update", user=user, detail=detail)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除用户")
async def delete_user(
    request: Request,
    user_id: int,
    current_admin: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    _attach_target(request, "admin.user.delete", user_id)
    def _delete(db) -> dict:
        user = service.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
        if user.id == current_admin.user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前登录用户")
        service.assert_can_manage_users(current_admin, [user])
        snapshot = user_snapshot(user) | {"id": user.id, "username": user.username}
        service.delete_user(db, user)
        snapshot["soft_deleted_at"] = user.deleted_at.isoformat() if user.deleted_at else None
        return snapshot

    user = await database_executor.run(_delete)
    audit_service.attach_audit_context(
        request.state,
        action="admin.user.delete",
        resource_type="user",
        resource_id=user["id"],
        target_summary=f"用户 {user['username']} (ID {user['id']})",
        detail={"deleted": user},
    )


@router.put("/users/{user_id}/scopes", response_model=AdminUserOut, summary="更新用户权限范围")
async def update_user_scopes(
    request: Request,
    user_id: int,
    payload: AdminUserScopesUpdate,
    current_admin: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    _attach_target(request, "admin.user.scopes.update", user_id)
    try:
        def _update_scopes(db) -> tuple[AdminUserOut, dict]:
            user = service.get_user_by_id(db, user_id)
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
            if user.id == current_admin.user_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改自己的权限范围")
            service.assert_can_manage_users(current_admin, [user])
            before_scopes = list(user.scope_overrides_list or ())
            updated_user = service.update_user_scopes(db, user, payload.scopes)
            after_scopes = list(updated_user.scope_overrides_list or ())
            detail = {
                "before_scopes": before_scopes,
                "after_scopes": after_scopes,
                "added_scopes": sorted(set(after_scopes) - set(before_scopes)),
                "removed_scopes": sorted(set(before_scopes) - set(after_scopes)),
            }
            return AdminUserOut.model_validate(updated_user), detail

        updated_user, detail = await database_executor.run(_update_scopes)
        audit_service.attach_user_audit_context(
            request.state, action="admin.user.scopes.update", user=updated_user, detail=detail
        )
        return updated_user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
