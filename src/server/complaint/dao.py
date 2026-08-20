# -*- coding: utf-8 -*-
"""用户投诉数据访问层。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.server.dao.dao_base import BaseDAO
from .models import Complaint, ComplaintStatus


class ComplaintDAO(BaseDAO):
    """用户投诉记录的写入与查询。"""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create(
        self,
        *,
        subject: str,
        content: str,
        contact: str | None,
        reporter_user_id: int,
    ) -> Complaint:
        complaint = Complaint(
            subject=subject,
            content=content,
            contact=contact,
            reporter_user_id=reporter_user_id,
            status=ComplaintStatus.PENDING,
        )
        self.db_session.add(complaint)
        self.db_session.flush()
        self.db_session.refresh(complaint)
        return complaint
