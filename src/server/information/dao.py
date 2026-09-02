# -*- coding: utf-8 -*-
"""信息发布数据访问层。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.server.dao.dao_base import BaseDAO
from .models import (
    InformationPost,
    InformationStatus,
    PublisherVerification,
    PublisherVerificationStatus,
)


class InformationPostDAO(BaseDAO):
    """分类信息发布记录的查询与写入。"""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create(
        self,
        *,
        title: str,
        category: str,
        content: str,
        contact_name: str,
        poster_user_id: int,
        price: str | None = None,
        contact_phone: str | None = None,
        attributes: dict[str, str] | None = None,
        publisher_verification_id: int | None = None,
    ) -> InformationPost:
        post = InformationPost(
            title=title,
            category=category,
            price=price,
            content=content,
            attributes=attributes,
            contact_name=contact_name,
            contact_phone=contact_phone,
            poster_user_id=poster_user_id,
            publisher_verification_id=publisher_verification_id,
            status=InformationStatus.PENDING,
            view_count=0,
            is_top=False,
        )
        self.db_session.add(post)
        self.db_session.flush()
        self.db_session.refresh(post)
        return post

    def get(self, post_id: int) -> InformationPost | None:
        return (
            self.db_session.query(InformationPost)
            .filter(InformationPost.id == post_id)
            .first()
        )

    def increment_view_count(self, post: InformationPost) -> InformationPost:
        post.view_count = (post.view_count or 0) + 1
        self.db_session.flush()
        return post

    def list_public(
        self,
        *,
        category: str | None,
        keyword: str | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[list[InformationPost], int]:
        query = self.db_session.query(InformationPost).join(
            PublisherVerification,
            PublisherVerification.id == InformationPost.publisher_verification_id,
        ).filter(
            InformationPost.status == InformationStatus.APPROVED,
            InformationPost.withdrawn_at.is_(None),
            PublisherVerification.status == PublisherVerificationStatus.APPROVED,
            or_(
                PublisherVerification.document_long_term.is_(True),
                PublisherVerification.document_valid_until >= datetime.now(timezone.utc).date(),
            ),
        )
        if category:
            query = query.filter(InformationPost.category == category)
        if keyword:
            pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    InformationPost.title.ilike(pattern),
                    InformationPost.content.ilike(pattern),
                )
            )
        total = query.count()
        ordered = query.order_by(*self._ordering(sort))
        items = (
            ordered.offset((page - 1) * page_size).limit(page_size).all()
        )
        return items, total

    def list_mine(self, user_id: int) -> list[InformationPost]:
        return (
            self.db_session.query(InformationPost)
            .filter(InformationPost.poster_user_id == user_id)
            .order_by(InformationPost.created_at.desc(), InformationPost.id.desc())
            .all()
        )

    def list_admin(
        self,
        *,
        status: InformationStatus | None,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[InformationPost], int]:
        query = self.db_session.query(InformationPost)
        if status is not None:
            query = query.filter(InformationPost.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    InformationPost.title.ilike(pattern),
                    InformationPost.content.ilike(pattern),
                    InformationPost.contact_name.ilike(pattern),
                    InformationPost.contact_phone.ilike(pattern),
                )
            )
        total = query.count()
        items = (
            query.order_by(InformationPost.created_at.desc(), InformationPost.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    @staticmethod
    def _ordering(sort: str):
        created = (InformationPost.created_at.desc(), InformationPost.id.desc())
        if sort == "hot":
            return (InformationPost.view_count.desc(),) + created
        if sort == "recommended":
            return (InformationPost.is_top.desc(),) + created
        return created

    def update_status(
        self,
        post: InformationPost,
        *,
        status: InformationStatus,
        reject_reason: str | None = None,
        approved: bool = False,
        reviewer_user_id: int,
    ) -> InformationPost:
        post.status = status
        post.reject_reason = reject_reason
        post.reviewed_by_user_id = reviewer_user_id
        post.reviewed_at = datetime.now(timezone.utc)
        if approved:
            post.approved_at = datetime.now(timezone.utc)
        else:
            post.approved_at = None
        self.db_session.flush()
        return post

    def set_top(self, post: InformationPost, *, on: bool) -> InformationPost:
        post.is_top = on
        self.db_session.flush()
        return post

    def withdraw(self, post: InformationPost, reason: str) -> InformationPost:
        post.withdrawn_at = datetime.now(timezone.utc)
        post.withdrawn_reason = reason
        post.is_top = False
        self.db_session.flush()
        return post
