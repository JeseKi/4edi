from __future__ import annotations
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.server.auth.models import User
from src.server.auth.schemas import UserStatus
from ..dao import NotificationDAO
from ..models import Notification, NotificationRecipient


@dataclass(frozen=True)
class PublishNotification:
    title: str
    body_markdown: str
    audience: str
    recipient_user_ids: tuple[int, ...] = ()
    created_by_user_id: int | None = None
    idempotency_key: str | None = None


def publish_notification(
    db: Session, command: PublishNotification
) -> tuple[Notification, int]:
    dao = NotificationDAO(db)
    if command.idempotency_key:
        existing = dao.get_by_key(command.idempotency_key)
        if existing:
            count = int(
                db.query(NotificationRecipient)
                .filter(NotificationRecipient.notification_id == existing.id)
                .count()
            )
            return existing, count
    if command.audience == "active_users":
        user_ids = list(
            db.scalars(
                select(User.id).where(
                    User.status == UserStatus.ACTIVE, User.deleted_at.is_(None)
                )
            )
        )
    elif command.audience == "users" and command.recipient_user_ids:
        user_ids = sorted(set(command.recipient_user_ids))
        active_ids = set(
            db.scalars(
                select(User.id).where(
                    User.id.in_(user_ids),
                    User.status == UserStatus.ACTIVE,
                    User.deleted_at.is_(None),
                )
            )
        )
        if active_ids != set(user_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="活跃用户不存在"
            )
    else:
        raise HTTPException(status_code=422, detail="无效的接收范围")
    item = dao.create(
        id=secrets.token_hex(16),
        title=command.title.strip(),
        body_markdown=command.body_markdown.strip(),
        created_by_user_id=command.created_by_user_id,
        idempotency_key=command.idempotency_key,
    )
    dao.add_recipients(item.id, user_ids)
    return item, len(user_ids)


def _out(row):
    recipient, item = row
    return {
        "id": item.id,
        "title": item.title,
        "body_markdown": item.body_markdown,
        "created_at": item.created_at,
        "read_at": recipient.read_at,
    }


def list_notifications(db: Session, user_id: int, offset: int, limit: int):
    rows, total = NotificationDAO(db).list_for_user(user_id, offset, limit)
    return [_out(row) for row in rows], total


def notification_summary(db: Session, user_id: int, limit: int):
    dao = NotificationDAO(db)
    rows, _ = dao.list_for_user(user_id, 0, limit)
    return dao.unread_count(user_id), [_out(row) for row in rows]


def get_notification(db: Session, user_id: int, notification_id: str):
    row = NotificationDAO(db).get_for_user(notification_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="消息不存在")
    return _out(row)


def mark_read(db: Session, user_id: int, notification_id: str):
    if not NotificationDAO(db).get_for_user(notification_id, user_id):
        raise HTTPException(status_code=404, detail="消息不存在")
    NotificationDAO(db).mark_read(notification_id, user_id, datetime.now(timezone.utc))


def mark_all_read(db: Session, user_id: int):
    return NotificationDAO(db).mark_all_read(user_id, datetime.now(timezone.utc))


def active_recipient_options(db: Session):
    return [
        {"id": u.id, "username": u.username, "name": u.name}
        for u in db.scalars(
            select(User)
            .where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
            .order_by(User.username)
        )
    ]


def list_published_notifications(db: Session, offset: int, limit: int):
    rows, total = NotificationDAO(db).list_all(offset, limit)
    return [{"id": item.id, "title": item.title, "body_markdown": item.body_markdown, "recipient_count": count, "created_at": item.created_at, "updated_at": item.updated_at} for item, count in rows], total


def update_notification(db: Session, notification_id: str, title: str, body_markdown: str):
    dao = NotificationDAO(db)
    item = dao.get(notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="消息不存在")
    item = dao.update(item, title=title.strip(), body_markdown=body_markdown.strip())
    return {"id": item.id, "title": item.title, "body_markdown": item.body_markdown, "recipient_count": dao.recipient_count(item.id), "created_at": item.created_at, "updated_at": item.updated_at}
