# -*- coding: utf-8 -*-
"""Persistent audit event model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="low", index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    action_label: Mapped[str | None] = mapped_column(String(120), default=None)
    method: Mapped[str | None] = mapped_column(String(10), default=None, index=True)
    path: Mapped[str | None] = mapped_column(String(500), default=None)
    path_template: Mapped[str | None] = mapped_column(String(500), default=None)
    http_status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    actor_username: Mapped[str | None] = mapped_column(String(80), default=None)
    actor_role: Mapped[str | None] = mapped_column(String(40), default=None)
    actor_identifier: Mapped[str | None] = mapped_column(String(255), default=None)
    resource_type: Mapped[str | None] = mapped_column(String(80), default=None, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(120), default=None)
    target_summary: Mapped[str | None] = mapped_column(String(500), default=None)
    request_id: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    client_ip: Mapped[str | None] = mapped_column(String(80), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(500), default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
