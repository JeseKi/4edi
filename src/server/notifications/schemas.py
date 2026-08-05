from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

NOTIFICATION_ID_PATTERN = r"^[a-f0-9]{32}$"


class NotificationOut(BaseModel):
    id: str = Field(pattern=NOTIFICATION_ID_PATTERN)
    title: str
    body_markdown: str
    created_at: datetime
    read_at: datetime | None


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    offset: int
    limit: int


class NotificationSummaryOut(BaseModel):
    unread_count: int
    items: list[NotificationOut]


class MarkAllReadOut(BaseModel):
    marked_count: int


class NotificationRecipientOption(BaseModel):
    id: int
    username: str
    name: str | None


class AdminNotificationCreate(BaseModel):
    audience: Literal["users", "active_users"]
    recipient_user_ids: list[int] = Field(default_factory=list)
    title: str = Field(min_length=1, max_length=200)
    body_markdown: str = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def validate_recipient(self):
        if self.audience == "users" and not self.recipient_user_ids:
            raise ValueError("请选择接收用户")
        if self.audience == "active_users" and self.recipient_user_ids:
            raise ValueError("全体通知不能指定用户")
        return self


class AdminNotificationPublishedOut(BaseModel):
    id: str
    recipient_count: int
    created_at: datetime


class AdminNotificationOut(BaseModel):
    id: str
    title: str
    body_markdown: str
    recipient_count: int
    created_at: datetime
    updated_at: datetime


class AdminNotificationListOut(BaseModel):
    items: list[AdminNotificationOut]
    total: int
    offset: int
    limit: int


class AdminNotificationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body_markdown: str = Field(min_length=1, max_length=20000)
