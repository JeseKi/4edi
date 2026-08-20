# -*- coding: utf-8 -*-
"""用户投诉短事务（请求内同步完成，无需后台任务）。"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..dao import ComplaintDAO


def create_complaint(db: Session, user_id: int, payload: dict) -> object:
    """创建一条用户投诉并记录提交人。

    校验在 Pydantic 层与这里双重兜底（空字符串、超长由 schema 负责），
    这里保证落库前关键字段非空。
    """
    subject = (payload.get("subject") or "").strip()
    content = (payload.get("content") or "").strip()
    contact = (payload.get("contact") or "").strip() or None

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="投诉对象不能为空"
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="投诉说明不能为空"
        )

    dao = ComplaintDAO(db)
    return dao.create(
        subject=subject,
        content=content,
        contact=contact,
        reporter_user_id=user_id,
    )
