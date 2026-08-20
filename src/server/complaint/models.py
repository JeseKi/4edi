# -*- coding: utf-8 -*-
"""用户投诉数据模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ComplaintStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"


class Complaint(Base):
    """一条用户提交的投诉记录。

    投诉内容自由填写（投诉对象/说明/可选联系方式），不强制关联具体信息
    条目；提交后默认进入「待处理」，由运营在后台处理（本期仅落库）。
    """

    __tablename__ = "complaints"
    __table_args__ = (
        Index("ix_complaints_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(120), default=None)
    reporter_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        SQLEnum(ComplaintStatus), nullable=False, default=ComplaintStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
