# -*- coding: utf-8 -*-
"""Audit service tests."""

from sqlalchemy.orm import Session

from src.server.audit import service
from src.server.audit.models import AuditEvent


def test_create_event_sanitizes_sensitive_detail(test_db_session: Session):
    event = service.create_event(
        test_db_session,
        outcome="success",
        action="test.action",
        detail={
            "username": "alice",
            "password": "secret",
            "nested": {"access_token": "token-value", "count": 3},
        },
    )

    test_db_session.refresh(event)
    out = service.to_out(event)

    assert out.action == "test.action"
    assert out.priority == "low"
    assert out.detail["username"] == "alice"
    assert out.detail["password"] == "[REDACTED]"
    assert out.detail["nested"] == {
        "access_token": "[REDACTED]",
        "count": 3,
    }


def test_list_events_filters_by_outcome_and_keyword(test_db_session: Session):
    service.create_event(
        test_db_session,
        outcome="success",
        action="alpha.create",
        target_summary="Alpha Target",
    )
    service.create_event(
        test_db_session,
        outcome="failure",
        action="beta.delete",
        target_summary="Beta Target",
    )

    items, total = service.list_events(
        test_db_session,
        page=1,
        page_size=10,
        q="beta",
        outcome="failure",
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].action == "beta.delete"
    assert test_db_session.query(AuditEvent).count() == 2


def test_priority_defaults_and_high_priority_action_classification(test_db_session: Session):
    low_event = service.create_event(
        test_db_session, outcome="success", action="example.item.create"
    )
    high_event = service.create_event(
        test_db_session, outcome="success", action="admin.user.delete"
    )

    assert low_event.priority == "low"
    assert high_event.priority == "high"


def test_action_label_round_trips_through_output(test_db_session: Session):
    event = service.create_event(
        test_db_session,
        outcome="success",
        action="files.upload_intent.create",
        action_label="创建文件上传意图",
    )
    out = service.to_out(event)
    assert out.action_label == "创建文件上传意图"

    bare_event = service.create_event(
        test_db_session,
        outcome="success",
        action="example.task.started",
    )
    assert service.to_out(bare_event).action_label is None
