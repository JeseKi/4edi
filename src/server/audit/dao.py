# -*- coding: utf-8 -*-
"""Audit event DAO."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from src.server.dao.dao_base import BaseDAO

from .models import AuditEvent


class AuditEventDAO(BaseDAO):
    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create(self, event: AuditEvent) -> AuditEvent:
        self.db_session.add(event)
        self.db_session.flush()
        self.db_session.refresh(event)
        return event

    def create_many(self, events: list[AuditEvent]) -> None:
        self.db_session.add_all(events)
        self.db_session.flush()

    def list_filtered(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        outcome: str | None = None,
        method: str | None = None,
        actor_user_id: int | None = None,
        resource_type: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> tuple[list[AuditEvent], int]:
        query = self._filtered_query(
            q=q,
            outcome=outcome,
            method=method,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            created_from=created_from,
            created_to=created_to,
        )
        total = query.count()
        items = (
            query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def _filtered_query(
        self,
        *,
        q: str | None,
        outcome: str | None,
        method: str | None,
        actor_user_id: int | None,
        resource_type: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> Query:
        query = self.db_session.query(AuditEvent)
        if outcome:
            query = query.filter(AuditEvent.outcome == outcome)
        if method:
            query = query.filter(AuditEvent.method == method.upper())
        if actor_user_id is not None:
            query = query.filter(AuditEvent.actor_user_id == actor_user_id)
        if resource_type:
            query = query.filter(AuditEvent.resource_type == resource_type)
        if created_from is not None:
            query = query.filter(AuditEvent.created_at >= created_from)
        if created_to is not None:
            query = query.filter(AuditEvent.created_at <= created_to)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.filter(
                or_(
                    AuditEvent.action.ilike(pattern),
                    AuditEvent.path.ilike(pattern),
                    AuditEvent.path_template.ilike(pattern),
                    AuditEvent.actor_username.ilike(pattern),
                    AuditEvent.actor_identifier.ilike(pattern),
                    AuditEvent.resource_type.ilike(pattern),
                    AuditEvent.resource_id.ilike(pattern),
                    AuditEvent.target_summary.ilike(pattern),
                    AuditEvent.request_id.ilike(pattern),
                )
            )
        return query
