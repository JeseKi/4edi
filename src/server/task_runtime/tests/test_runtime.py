from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import threading
from time import sleep

import pytest
from sqlalchemy.orm import Session, sessionmaker

from src.server.config import global_config
from src.server.task_runtime import (
    RetryableTaskError,
    TaskDefinition,
    TaskPolicy,
    TaskQueue,
    TaskRuntime,
)
from src.server.task_runtime.dao import BackgroundJobDAO
from src.server.task_runtime.models import BackgroundJob


def _session_runner(test_db_session: Session, close_count: list[int]):
    factory = sessionmaker(bind=test_db_session.get_bind(), autocommit=False, autoflush=False)
    lock = threading.Lock()

    def run(operation):
        with lock:
            db = factory()
            try:
                result = operation(db)
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
                close_count.append(1)

    return run


@pytest.mark.asyncio
async def test_runtime_retries_and_closes_each_database_phase(test_db_session: Session):
    closes: list[int] = []
    runner = _session_runner(test_db_session, closes)
    runtime = TaskRuntime(session_runner=runner)
    calls = 0

    def handler(context, _payload):
        nonlocal calls
        calls += 1
        context.run_db(lambda db: db.query(BackgroundJob).count())
        if calls == 1:
            raise RetryableTaskError("temporary upstream failure")

    definition = TaskDefinition(
        name="test.retry",
        queue=TaskQueue.IO,
        handler=handler,
        policy=TaskPolicy(max_attempts=2, retry_delays=(0,)),
    )
    runtime.register(definition)
    await runtime.start()
    try:
        job_id = runner(lambda db: runtime.enqueue(db, definition, None))
        job_state = None
        for _ in range(100):
            job_state = runner(lambda db: _read_job_state(db, job_id))
            if job_state is not None and job_state[0] in {"succeeded", "failed"}:
                break
            await asyncio.sleep(0.01)
        assert job_state is not None
        assert job_state[0] == "succeeded"
        assert job_state[1] == 2
        assert calls == 2
        assert len(closes) >= 6
    finally:
        await runtime.stop()


def _read_job_state(db: Session, job_id: str) -> tuple[str, int] | None:
    job = db.get(BackgroundJob, job_id)
    if job is None:
        return None
    return job.status, job.attempt_count


def _read_job_error_type(db: Session, job_id: str) -> str | None:
    job = db.get(BackgroundJob, job_id)
    return job.error_type if job is not None else None


@pytest.mark.asyncio
async def test_runtime_recovers_expired_lease(test_db_session: Session):
    closes: list[int] = []
    runner = _session_runner(test_db_session, closes)
    handled_payloads: list[str] = []
    definition = TaskDefinition(
        name="test.recover",
        queue=TaskQueue.BATCH,
        handler=lambda _context, payload: handled_payloads.append(payload),
        policy=TaskPolicy(max_attempts=2),
    )
    runtime = TaskRuntime(session_runner=runner)
    runtime.register(definition)
    expired_at = datetime.now(timezone.utc) - timedelta(
        seconds=global_config.tasks.job_lease_seconds + 1
    )

    def create_expired_job(db: Session) -> None:
        BackgroundJobDAO(db).create(
            id="expired-job",
            task_name=definition.name,
            queue_name=definition.queue.value,
            status="running",
            attempt_count=1,
            max_attempts=2,
            metadata_json=json.dumps({"version": 1, "payload": "resume", "reference": {}}),
            started_at=expired_at,
            updated_at=expired_at,
        )

    runner(create_expired_job)
    await runtime.start()
    try:
        state = await _wait_for_terminal_state(runner, "expired-job")
        assert state == ("succeeded", 2)
        assert handled_payloads == ["resume"]
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_marks_invalid_persisted_payload_failed(test_db_session: Session):
    closes: list[int] = []
    runner = _session_runner(test_db_session, closes)
    definition = TaskDefinition(
        name="test.invalid-payload",
        queue=TaskQueue.BATCH,
        handler=lambda _context, _payload: pytest.fail("不应执行损坏 payload"),
    )
    runtime = TaskRuntime(session_runner=runner)
    runtime.register(definition)

    def create_invalid_job(db: Session) -> None:
        BackgroundJobDAO(db).create(
            id="invalid-job",
            task_name=definition.name,
            queue_name=definition.queue.value,
            status="queued",
            max_attempts=1,
            metadata_json="{}",
        )

    runner(create_invalid_job)
    await runtime.start()
    try:
        state = await _wait_for_terminal_state(runner, "invalid-job")
        assert state == ("failed", 1)
        assert runner(lambda db: _read_job_error_type(db, "invalid-job")) == "TaskPayloadError"
    finally:
        await runtime.stop()


def test_enqueue_can_delay_first_execution(test_db_session: Session):
    closes: list[int] = []
    runner = _session_runner(test_db_session, closes)
    definition = TaskDefinition(
        name="test.delayed",
        queue=TaskQueue.IO,
        handler=lambda _context, _payload: None,
    )
    runtime = TaskRuntime(definitions=(definition,), session_runner=runner)
    not_before = datetime.now(timezone.utc) + timedelta(minutes=1)
    job_id = runner(
        lambda db: runtime.enqueue(db, definition, {"kind": "delayed"}, not_before=not_before)
    )

    job_state = runner(
        lambda db: (
            db.get(BackgroundJob, job_id).status,
            db.get(BackgroundJob, job_id).next_attempt_at,
        )
    )
    assert job_state[0] == "retry_wait"
    assert job_state[1] == not_before.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_sqlite_runtime_serializes_different_queues(test_db_session: Session):
    closes: list[int] = []
    runner = _session_runner(test_db_session, closes)
    active_handlers = 0
    max_active_handlers = 0
    counter_lock = threading.Lock()

    def handler(_context, _payload) -> None:
        nonlocal active_handlers, max_active_handlers
        with counter_lock:
            active_handlers += 1
            max_active_handlers = max(max_active_handlers, active_handlers)
        try:
            sleep(0.03)
        finally:
            with counter_lock:
                active_handlers -= 1

    definitions = (
        TaskDefinition(name="test.sqlite.io", queue=TaskQueue.IO, handler=handler),
        TaskDefinition(name="test.sqlite.batch", queue=TaskQueue.BATCH, handler=handler),
    )
    runtime = TaskRuntime(
        definitions=definitions,
        session_runner=runner,
        sqlite_single_worker=True,
    )
    job_ids = [
        runner(lambda db, definition=definition: runtime.enqueue(db, definition, None))
        for definition in definitions
    ]
    await runtime.start()
    try:
        states = [await _wait_for_terminal_state(runner, job_id) for job_id in job_ids]
        assert states == [("succeeded", 1), ("succeeded", 1)]
        assert max_active_handlers == 1
    finally:
        await runtime.stop()


async def _wait_for_terminal_state(
    runner, job_id: str
) -> tuple[str, int] | None:
    for _ in range(100):
        state = runner(lambda db: _read_job_state(db, job_id))
        if state is not None and state[0] in {"succeeded", "failed"}:
            return state
        await asyncio.sleep(0.01)
    return None
