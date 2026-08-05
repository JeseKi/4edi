# -*- coding: utf-8 -*-
"""Background batching runtime for low-priority audit events."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from loguru import logger

from src.server.database_executor import DatabaseExecutorRunner

from .dao import AuditEventDAO
from .service import build_event


class AuditRuntime:
    def __init__(
        self,
        database_executor: DatabaseExecutorRunner,
        *,
        flush_seconds: float = 5,
        batch_size: int = 100,
        queue_size: int = 10_000,
    ):
        self._database_executor = database_executor
        self.flush_seconds = flush_seconds
        self.batch_size = batch_size
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="audit-low-priority-writer")

    def enqueue(self, event: Mapping[str, Any]) -> bool:
        try:
            self.queue.put_nowait(dict(event))
            return True
        except asyncio.QueueFull:
            logger.error("低优先级审计队列已满，事件被丢弃")
            return False

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.flush()

    async def flush(self) -> None:
        events = self._drain()
        if not events:
            return
        try:
            await self._database_executor.run(
                lambda db: AuditEventDAO(db).create_many(
                    [build_event(**event) for event in events]
                )
            )
        except Exception:
            logger.exception("批量写入低优先级审计日志失败")
            for event in events:
                self.enqueue(event)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.flush_seconds)
            await self.flush()

    def _drain(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while len(events) < self.batch_size:
            try:
                events.append(self.queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events
