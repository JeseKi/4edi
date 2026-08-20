# -*- coding: utf-8 -*-
"""用户投诉 Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ComplaintCreateIn(BaseModel):
    subject: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=2000)
    contact: str | None = Field(default=None, max_length=120)

    @field_validator("subject")
    @classmethod
    def _strip_subject(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("投诉对象不能为空")
        return stripped

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("投诉说明不能为空")
        return stripped

    @field_validator("contact")
    @classmethod
    def _strip_contact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ComplaintOut(BaseModel):
    id: int
    subject: str
    content: str
    contact: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
