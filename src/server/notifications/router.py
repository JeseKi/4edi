from __future__ import annotations
from fastapi import APIRouter, Depends, Query, Request, Security, status
from src.server.audit import service as audit_service
from src.server.auth.dependencies import AuthenticatedPrincipal, get_current_principal
from src.server.auth.service.scopes import (
    SCOPE_ADMIN_NOTIFICATIONS_WRITE,
    SCOPE_NOTIFICATIONS_READ,
)
from src.server.database_executor import DatabaseExecutor, get_database_executor
from . import service
from .schemas import (
    AdminNotificationCreate,
    AdminNotificationListOut,
    AdminNotificationOut,
    AdminNotificationPublishedOut,
    AdminNotificationUpdate,
    MarkAllReadOut,
    NotificationListOut,
    NotificationOut,
    NotificationRecipientOption,
    NotificationSummaryOut,
)

router = APIRouter(tags=["站内消息"])


@router.get("/api/notifications", response_model=NotificationListOut, summary="查询通知列表")
async def list_messages(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_NOTIFICATIONS_READ]
    ),
):
    items, total = await database_executor.run(
        lambda db: service.list_notifications(db, principal.user_id, offset, limit)
    )
    return NotificationListOut(
        items=[NotificationOut.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/api/notifications/summary", response_model=NotificationSummaryOut, summary="查询未读通知摘要")
async def summary(
    limit: int = Query(5, ge=1, le=10),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_NOTIFICATIONS_READ]
    ),
):
    count, items = await database_executor.run(
        lambda db: service.notification_summary(db, principal.user_id, limit)
    )
    return NotificationSummaryOut(
        unread_count=count,
        items=[NotificationOut.model_validate(item) for item in items],
    )


@router.get("/api/notifications/{notification_id}", response_model=NotificationOut, summary="获取通知详情")
async def detail(
    notification_id: str,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_NOTIFICATIONS_READ]
    ),
):
    return await database_executor.run(
        lambda db: service.get_notification(db, principal.user_id, notification_id)
    )


@router.post(
    "/api/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT, summary="标记通知已读"
)
async def read(
    notification_id: str,
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_NOTIFICATIONS_READ]
    ),
):
    audit_service.attach_audit_context(
        request.state,
        action="notifications.read",
        resource_type="notification",
        resource_id=notification_id,
        target_summary=f"通知 {notification_id}",
    )
    await database_executor.run(
        lambda db: service.mark_read(db, principal.user_id, notification_id)
    )


@router.post("/api/notifications/read-all", response_model=MarkAllReadOut, summary="全部标记已读")
async def read_all(
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_NOTIFICATIONS_READ]
    ),
):
    marked_count = await database_executor.run(
        lambda db: service.mark_all_read(db, principal.user_id)
    )
    audit_service.attach_audit_context(
        request.state,
        action="notifications.read_all",
        resource_type="notification",
        target_summary=f"全部已读（{marked_count} 条）",
        detail={"marked_count": marked_count},
    )
    return MarkAllReadOut(marked_count=marked_count)


@router.get(
    "/api/admin/notifications/recipients",
    response_model=list[NotificationRecipientOption],
    summary="查询通知接收人选项",
)
async def recipients(
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    _: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_ADMIN_NOTIFICATIONS_WRITE]
    ),
):
    return await database_executor.run(service.active_recipient_options)


@router.get("/api/admin/notifications", response_model=AdminNotificationListOut, summary="查询已发布通知")
async def list_published(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), database_executor: DatabaseExecutor = Depends(get_database_executor), _: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_ADMIN_NOTIFICATIONS_WRITE])):
    items, total = await database_executor.run(lambda db: service.list_published_notifications(db, offset, limit))
    return AdminNotificationListOut(items=[AdminNotificationOut.model_validate(item) for item in items], total=total, offset=offset, limit=limit)


@router.post(
    "/api/admin/notifications",
    response_model=AdminNotificationPublishedOut,
    status_code=status.HTTP_201_CREATED,
    summary="发布通知",
)
async def publish(
    payload: AdminNotificationCreate,
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
    principal: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=[SCOPE_ADMIN_NOTIFICATIONS_WRITE]
    ),
):
    def _publish(db):
        item, count = service.publish_notification(
            db,
            service.PublishNotification(
                title=payload.title,
                body_markdown=payload.body_markdown,
                audience=payload.audience,
                recipient_user_ids=tuple(payload.recipient_user_ids),
                created_by_user_id=principal.user_id,
            ),
        )
        return item.id, count, item.created_at

    notification_id, count, created_at = await database_executor.run(_publish)
    audit_service.attach_audit_context(
        request.state,
        action="admin.notification.publish",
        resource_type="notification",
        resource_id=notification_id,
        target_summary="全体活跃用户"
        if payload.audience == "active_users"
        else f"指定 {count} 位用户",
        detail={"audience": payload.audience, "recipient_count": count},
    )
    return AdminNotificationPublishedOut(
        id=notification_id, recipient_count=count, created_at=created_at
    )


@router.patch("/api/admin/notifications/{notification_id}", response_model=AdminNotificationOut, summary="更新通知")
async def update_published(notification_id: str, payload: AdminNotificationUpdate, request: Request, database_executor: DatabaseExecutor = Depends(get_database_executor), _: AuthenticatedPrincipal = Security(get_current_principal, scopes=[SCOPE_ADMIN_NOTIFICATIONS_WRITE])):
    item = await database_executor.run(lambda db: service.update_notification(db, notification_id, payload.title, payload.body_markdown))
    audit_service.attach_audit_context(request.state, action="admin.notification.update", resource_type="notification", resource_id=notification_id)
    return AdminNotificationOut.model_validate(item)
