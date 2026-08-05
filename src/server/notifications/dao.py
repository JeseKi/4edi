from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import Notification, NotificationRecipient


class NotificationDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_by_key(self, key: str) -> Notification | None:
        return self.db.scalar(
            select(Notification).where(Notification.idempotency_key == key)
        )

    def create(self, **values) -> Notification:
        item = Notification(**values)
        self.db.add(item)
        self.db.flush()
        return item

    def add_recipients(self, notification_id: str, user_ids: list[int]) -> None:
        self.db.add_all(
            [
                NotificationRecipient(notification_id=notification_id, user_id=user_id)
                for user_id in user_ids
            ]
        )
        self.db.flush()

    def list_for_user(self, user_id: int, offset: int, limit: int):
        statement = (
            select(NotificationRecipient, Notification)
            .join(
                Notification, Notification.id == NotificationRecipient.notification_id
            )
            .where(NotificationRecipient.user_id == user_id)
        )
        total = int(
            self.db.scalar(
                select(func.count())
                .select_from(NotificationRecipient)
                .where(NotificationRecipient.user_id == user_id)
            )
            or 0
        )
        return list(
            self.db.execute(
                statement.order_by(Notification.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ), total

    def get_for_user(self, notification_id: str, user_id: int):
        statement = (
            select(NotificationRecipient, Notification)
            .join(
                Notification, Notification.id == NotificationRecipient.notification_id
            )
            .where(
                NotificationRecipient.notification_id == notification_id,
                NotificationRecipient.user_id == user_id,
            )
        )
        return self.db.execute(statement).first()

    def unread_count(self, user_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(NotificationRecipient)
                .where(
                    NotificationRecipient.user_id == user_id,
                    NotificationRecipient.read_at.is_(None),
                )
            )
            or 0
        )

    def mark_read(self, notification_id: str, user_id: int, now: datetime) -> bool:
        result = self.db.execute(
            update(NotificationRecipient)
            .where(
                NotificationRecipient.notification_id == notification_id,
                NotificationRecipient.user_id == user_id,
                NotificationRecipient.read_at.is_(None),
            )
            .values(read_at=now)
        )
        return result.rowcount > 0

    def mark_all_read(self, user_id: int, now: datetime) -> int:
        result = self.db.execute(
            update(NotificationRecipient)
            .where(
                NotificationRecipient.user_id == user_id,
                NotificationRecipient.read_at.is_(None),
            )
            .values(read_at=now)
        )
        return result.rowcount

    def list_all(self, offset: int, limit: int):
        count_statement = select(func.count()).select_from(Notification)
        total = int(self.db.scalar(count_statement) or 0)
        recipient_count = select(func.count()).where(NotificationRecipient.notification_id == Notification.id).correlate(Notification).scalar_subquery()
        items = list(self.db.execute(select(Notification, recipient_count.label("recipient_count")).order_by(Notification.created_at.desc()).offset(offset).limit(limit)))
        return items, total

    def get(self, notification_id: str) -> Notification | None:
        return self.db.get(Notification, notification_id)

    def recipient_count(self, notification_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(NotificationRecipient)
                .where(NotificationRecipient.notification_id == notification_id)
            )
            or 0
        )

    def update(self, item: Notification, *, title: str, body_markdown: str) -> Notification:
        item.title = title
        item.body_markdown = body_markdown
        self.db.flush()
        return item
