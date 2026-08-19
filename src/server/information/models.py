# -*- coding: utf-8 -*-
"""分类信息发布数据模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
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


class InformationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class InformationPost(Base):
    """一条分类信息发布记录。

    新发布的信息默认进入「待审核」，管理员通过后才对外展示；
    ``contact_phone`` 对游客隐藏（服务层打码）。
    """

    __tablename__ = "information_posts"
    __table_args__ = (
        Index("ix_information_posts_status_created", "status", "created_at"),
        Index("ix_information_posts_category_status", "category", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
    contact_name: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    poster_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[InformationStatus] = mapped_column(
        SQLEnum(InformationStatus), nullable=False, default=InformationStatus.PENDING
    )
    reject_reason: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    is_top: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
