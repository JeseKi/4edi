# -*- coding: utf-8 -*-
"""信息发布 Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from .constants import INFORMATION_CATEGORIES
from .models import InformationStatus, PublisherVerificationStatus

T = TypeVar("T")


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class CategoryAttributeOut(BaseModel):
    key: str
    label: str
    type: str
    options: list[str] | None = None


class CategoryOut(BaseModel):
    key: str
    name: str
    attributes: list[CategoryAttributeOut]


class PostCreateIn(BaseModel):
    category: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=120)
    price: str | None = Field(default=None, max_length=50)
    contact_name: str = Field(..., min_length=1, max_length=50)
    contact_phone: str = Field(..., min_length=5, max_length=32)
    content: str = Field(..., min_length=1, max_length=5000)
    attributes: dict[str, str] | None = None

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        if value not in INFORMATION_CATEGORIES:
            raise ValueError(f"未知信息分类：{value}")
        return value

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("详情内容不能为空")
        return stripped


class PostOut(BaseModel):
    """公开列表项（不包含手机号等联系方式）。"""

    id: int
    title: str
    category: str
    category_name: str
    price: str | None
    poster_username: str
    view_count: int
    is_top: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PostDetailOut(PostOut):
    """公开详情（手机号打码后返回）。"""

    content: str
    attributes: dict[str, str] | None
    contact_name: str
    contact_phone: str | None
    approved_at: datetime | None


class PostMineOut(PostDetailOut):
    """发布人视角（含完整手机号与审核状态）。"""

    status: InformationStatus
    reject_reason: str | None
    reviewed_by_user_id: int | None
    reviewed_at: datetime | None
    withdrawn_at: datetime | None
    withdrawn_reason: str | None

    model_config = {"from_attributes": True}


class PostAdminListOut(PostMineOut):
    """管理员列表项。"""

    poster_user_id: int
    publisher_verification_id: int | None
    publisher_real_name: str | None
    publisher_document_number_masked: str | None
    publisher_verification_valid: bool


class PostReviewIn(BaseModel):
    approved: bool
    reject_reason: str | None = Field(default=None, max_length=200)


class ContactOut(BaseModel):
    contact_name: str
    contact_phone: str


class PublisherVerificationCreateIn(BaseModel):
    real_name: str = Field(..., min_length=2, max_length=100)
    document_type: str = Field(..., pattern="^(resident_identity_card|passport)$")
    document_number: str = Field(..., min_length=5, max_length=64)
    document_front_asset_id: str = Field(..., min_length=32, max_length=32)
    document_back_asset_id: str | None = Field(default=None, min_length=32, max_length=32)
    document_valid_until: date | None = None
    document_long_term: bool = False


class PublisherVerificationReviewIn(BaseModel):
    approved: bool
    reject_reason: str | None = Field(default=None, max_length=300)


class PublisherVerificationOut(BaseModel):
    id: int
    user_id: int
    username: str
    real_name: str
    document_type: str
    document_number_masked: str
    document_front_asset_id: str
    document_back_asset_id: str | None
    document_valid_until: date | None
    document_long_term: bool
    status: PublisherVerificationStatus
    submitted_at: datetime
    reviewer_user_id: int | None
    reviewer_username: str | None
    reviewed_at: datetime | None
    reject_reason: str | None
    is_currently_valid: bool


class PublisherVerificationPageOut(BaseModel):
    items: list[PublisherVerificationOut]
    total: int
    page: int
    page_size: int
