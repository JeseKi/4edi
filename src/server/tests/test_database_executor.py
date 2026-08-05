from __future__ import annotations

import asyncio
from threading import Event

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.server.database_executor import (
    DatabaseExecutor,
    DatabaseExecutorOverloadedError,
    UnsafeDatabaseResultError,
)
from src.server.example_module.models import Item


def _session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'executor.db'}",
        connect_args={"check_same_thread": False},
    )
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.mark.asyncio
async def test_executor_queues_before_creating_the_next_session(tmp_path):
    engine, factory = _session_factory(tmp_path)
    created_sessions = 0
    started = Event()
    release = Event()

    def counted_factory() -> Session:
        nonlocal created_sessions
        created_sessions += 1
        return factory()

    executor = DatabaseExecutor(
        counted_factory, dialect="sqlite", max_workers=1, queue_timeout_seconds=1
    )
    try:
        first = asyncio.create_task(
            executor.run(lambda _db: (started.set(), release.wait(1), "first")[-1])
        )
        assert await asyncio.to_thread(started.wait, 1)

        second = asyncio.create_task(executor.run(lambda _db: "second"))
        await asyncio.sleep(0.02)
        assert created_sessions == 1
        assert executor.snapshot().waiting == 1

        release.set()
        assert await first == "first"
        assert await second == "second"
        assert created_sessions == 2
    finally:
        await executor.shutdown()
        engine.dispose()


@pytest.mark.asyncio
async def test_executor_rolls_back_and_closes_the_session_after_failure(tmp_path):
    engine, factory = _session_factory(tmp_path)
    with engine.begin() as connection:
        connection.execute(text("create table executor_records (id integer primary key)"))

    executor = DatabaseExecutor(
        factory, dialect="sqlite", max_workers=1, queue_timeout_seconds=1
    )
    try:
        def failing_operation(db: Session) -> None:
            db.execute(text("insert into executor_records (id) values (1)"))
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await executor.run(failing_operation)

        with engine.connect() as connection:
            assert connection.execute(text("select count(*) from executor_records")).scalar_one() == 0
        assert executor.snapshot().failed == 1
    finally:
        await executor.shutdown()
        engine.dispose()


@pytest.mark.asyncio
async def test_executor_rejects_session_results_before_commit(tmp_path):
    engine, factory = _session_factory(tmp_path)
    executor = DatabaseExecutor(
        factory, dialect="sqlite", max_workers=1, queue_timeout_seconds=1
    )
    try:
        with pytest.raises(UnsafeDatabaseResultError, match="Session"):
            await executor.run(lambda db: db)
        with pytest.raises(UnsafeDatabaseResultError, match="ORM"):
            await executor.run(lambda _db: Item(name="not-safe"))
        assert executor.snapshot().failed == 2
    finally:
        await executor.shutdown()
        engine.dispose()


@pytest.mark.asyncio
async def test_executor_returns_overload_without_borrowing_another_connection(tmp_path):
    engine, factory = _session_factory(tmp_path)
    created_sessions = 0
    started = Event()
    release = Event()

    def counted_factory() -> Session:
        nonlocal created_sessions
        created_sessions += 1
        return factory()

    executor = DatabaseExecutor(
        counted_factory, dialect="sqlite", max_workers=1, queue_timeout_seconds=0.02
    )
    try:
        first = asyncio.create_task(
            executor.run(lambda _db: (started.set(), release.wait(1), None)[-1])
        )
        assert await asyncio.to_thread(started.wait, 1)

        with pytest.raises(DatabaseExecutorOverloadedError):
            await executor.run(lambda _db: None)
        assert created_sessions == 1
        assert executor.snapshot().queue_timeouts == 1

        release.set()
        await first
    finally:
        await executor.shutdown()
        engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_request_keeps_its_slot_until_the_callback_finishes(tmp_path):
    engine, factory = _session_factory(tmp_path)
    started = Event()
    release = Event()
    second_started = Event()
    executor = DatabaseExecutor(
        factory, dialect="sqlite", max_workers=1, queue_timeout_seconds=1
    )
    try:
        first = asyncio.create_task(
            executor.run(lambda _db: (started.set(), release.wait(1), None)[-1])
        )
        assert await asyncio.to_thread(started.wait, 1)

        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

        second = asyncio.create_task(
            executor.run(lambda _db: (second_started.set(), "second")[-1])
        )
        await asyncio.sleep(0.02)
        assert not second_started.is_set()
        assert executor.snapshot().active == 1

        release.set()
        assert await second == "second"
    finally:
        await executor.shutdown()
        engine.dispose()
