from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RegulatoryEvidenceLink(Base):
    """只保存监管核验令牌的摘要，明文仅在创建时返回一次。"""

    __tablename__ = "regulatory_evidence_links"
    __table_args__ = (
        Index(
            "ix_reg_evidence_resource",
            "evidence_type",
            "resource_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    token_hint: Mapped[str] = mapped_column(String(8), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
