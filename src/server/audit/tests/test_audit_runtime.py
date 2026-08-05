# -*- coding: utf-8 -*-
"""Low-priority audit batching tests."""

import pytest
from collections.abc import Callable
from typing import TypeVar, cast

from sqlalchemy.orm import Session

from src.server.audit import runtime


_Result = TypeVar("_Result")


class _ImmediateExecutor:
    async def run(self, operation: Callable[[Session], _Result]) -> _Result:
        return operation(cast(Session, None))


@pytest.mark.asyncio
async def test_low_priority_runtime_flushes_queued_events(monkeypatch):
    persisted: list[dict] = []
    monkeypatch.setattr(
        runtime.AuditEventDAO,
        "create_many",
        lambda _self, events: persisted.extend(
            [{"action": event.action, "outcome": event.outcome} for event in events]
        ),
    )
    audit_runtime = runtime.AuditRuntime(
        _ImmediateExecutor(), flush_seconds=5, batch_size=100, queue_size=2
    )

    assert audit_runtime.enqueue({"action": "example.item.create", "outcome": "success"})
    await audit_runtime.flush()

    assert persisted == [{"action": "example.item.create", "outcome": "success"}]
    assert audit_runtime.queue.empty()


def test_low_priority_runtime_drops_when_queue_is_full():
    audit_runtime = runtime.AuditRuntime(
        _ImmediateExecutor(), flush_seconds=5, batch_size=100, queue_size=1
    )

    assert audit_runtime.enqueue({"action": "one"})
    assert not audit_runtime.enqueue({"action": "two"})
