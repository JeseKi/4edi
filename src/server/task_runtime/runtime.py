from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import json
import secrets
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.server.config import global_config
from src.server.database import run_in_new_session
from .dao import BackgroundJobDAO, ClaimedJob


class TaskQueue(StrEnum):
    IO = "io"
    NOTIFICATION = "notification"
    BATCH = "batch"


class RetryableTaskError(Exception):
    """仅此异常会触发任务定义声明的重试。"""


class TaskPayloadError(ValueError):
    """任务 payload 无法作为持久化 JSON 信封处理。"""


@dataclass(frozen=True)
class TaskPolicy:
    max_attempts: int = 3
    retry_delays: tuple[int, ...] = (1, 5, 25)


@dataclass(frozen=True)
class TaskReference:
    resource_type: str | None = None
    resource_id: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    queue: TaskQueue
    handler: Callable[["TaskContext", Any], None]
    on_cancelled: Callable[["TaskContext", Any], None] | None = None
    policy: TaskPolicy = field(default_factory=TaskPolicy)


class TaskContext:
    def __init__(
        self,
        job_id: str,
        attempt: int,
        session_runner: Callable[[Callable[[Session], Any]], Any] = run_in_new_session,
    ):
        self.job_id = job_id
        self.attempt = attempt
        self._session_runner = session_runner

    def run_db(self, operation: Callable[[Session], Any]) -> Any:
        """运行短数据库阶段；外部 I/O 不得放入这个 callback。"""
        return self._session_runner(operation)


class TaskRuntime:
    """基于数据库的持久化任务运行时。"""

    def __init__(
        self,
        definitions: Iterable[TaskDefinition] = (),
        session_runner: Callable[[Callable[[Session], Any]], Any] = run_in_new_session,
        *,
        sqlite_single_worker: bool = False,
    ) -> None:
        self._run_db = session_runner
        self._definitions: dict[str, TaskDefinition] = {}
        self._sqlite_single_worker = sqlite_single_worker
        self._configured_worker_counts = {
            TaskQueue.IO: global_config.tasks.io_workers,
            TaskQueue.NOTIFICATION: global_config.tasks.notification_workers,
            TaskQueue.BATCH: global_config.tasks.batch_workers,
        }
        for definition in definitions:
            self.register(definition)
        self._executor = ThreadPoolExecutor(
            max_workers=1 if sqlite_single_worker else sum(self._configured_worker_counts.values()),
            thread_name_prefix="template-task",
        )
        self._workers: list[asyncio.Task[None]] = []
        self._heartbeats: set[asyncio.Task[None]] = set()

    def register(self, definition: TaskDefinition) -> None:
        existing = self._definitions.get(definition.name)
        if existing is not None and existing != definition:
            raise ValueError(f"后台任务名称重复注册：{definition.name}")
        self._definitions[definition.name] = definition

    def enqueue(
        self,
        db: Session,
        definition: TaskDefinition,
        payload: Any,
        *,
        reference: TaskReference | None = None,
        not_before: datetime | None = None,
    ) -> str:
        """在调用方已有业务 Session 中持久化任务，不等待 worker。"""
        registered = self._definitions.get(definition.name)
        if registered != definition:
            raise ValueError(f"后台任务未注册：{definition.name}")
        reference = reference or TaskReference()
        metadata_json = _encode_envelope(payload, reference)
        job_id = secrets.token_hex(16)
        BackgroundJobDAO(db).create(
            id=job_id,
            task_name=definition.name,
            queue_name=definition.queue.value,
            status="retry_wait" if not_before is not None else "queued",
            max_attempts=definition.policy.max_attempts,
            resource_type=reference.resource_type,
            resource_id=reference.resource_id,
            request_id=reference.request_id,
            metadata_json=metadata_json,
            next_attempt_at=not_before,
        )
        return job_id

    async def start(self) -> None:
        recovered = await asyncio.to_thread(self._recover_expired_leases)
        if recovered:
            logger.warning("已重新排队 {} 个租约到期的后台任务", recovered)
        enabled_queues = {definition.queue for definition in self._definitions.values()}
        if self._sqlite_single_worker and enabled_queues:
            queues = tuple(queue for queue in TaskQueue if queue in enabled_queues)
            self._workers.append(
                asyncio.create_task(
                    self._sqlite_worker(queues), name="task-sqlite-worker"
                )
            )
            return
        for queue, count in self._configured_worker_counts.items():
            if queue not in enabled_queues:
                continue
            self._workers.extend(
                asyncio.create_task(self._worker(queue), name=f"task-{queue}-{index}")
                for index in range(count)
            )

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        for heartbeat in self._heartbeats:
            heartbeat.cancel()
        await asyncio.gather(*self._heartbeats, return_exceptions=True)
        self._executor.shutdown(wait=False, cancel_futures=True)

    async def _worker(self, queue_name: TaskQueue) -> None:
        while True:
            if not await self._claim_and_execute(queue_name):
                await asyncio.sleep(global_config.tasks.dispatch_poll_interval_seconds)

    async def _sqlite_worker(self, queues: tuple[TaskQueue, ...]) -> None:
        """SQLite 只有一个写者，所有队列共用一个执行槽位。"""
        queue_index = 0
        while True:
            queue_name = queues[queue_index % len(queues)]
            queue_index += 1
            if not await self._claim_and_execute(queue_name):
                await asyncio.sleep(global_config.tasks.dispatch_poll_interval_seconds)

    async def _claim_and_execute(self, queue_name: TaskQueue) -> bool:
        try:
            claimed = await asyncio.to_thread(self._claim_next, queue_name)
        except Exception:
            logger.exception("后台任务领取失败：{}", queue_name)
            return False
        if claimed is None:
            return False
        heartbeat = asyncio.create_task(self._heartbeat(claimed.id))
        self._heartbeats.add(heartbeat)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._execute, claimed)
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            self._heartbeats.discard(heartbeat)
        return True

    async def _heartbeat(self, job_id: str) -> None:
        while True:
            await asyncio.sleep(global_config.tasks.job_heartbeat_interval_seconds)
            touched = await asyncio.to_thread(self._touch_running, job_id)
            if not touched:
                return

    def _execute(self, claimed: ClaimedJob) -> None:
        definition = self._definitions.get(claimed.task_name)
        if definition is None:
            self._fail_unrecoverable(
                claimed.id,
                "TaskDefinitionNotRegistered",
                f"任务定义未注册：{claimed.task_name}",
            )
            return
        try:
            payload = _decode_payload(claimed.metadata_json)
        except TaskPayloadError as exc:
            self._fail_unrecoverable(claimed.id, exc.__class__.__name__, str(exc))
            return

        context = TaskContext(claimed.id, claimed.attempt_count, self._run_db)
        try:
            definition.handler(context, payload)
        except RetryableTaskError as exc:
            if claimed.attempt_count < definition.policy.max_attempts:
                delay = definition.policy.retry_delays[
                    min(
                        claimed.attempt_count - 1,
                        len(definition.policy.retry_delays) - 1,
                    )
                ]
                self._schedule_retry(
                    claimed.id,
                    exc,
                    datetime.now(timezone.utc) + timedelta(seconds=delay),
                )
                return
            self._finish(claimed.id, "failed", error=exc)
        except Exception as exc:
            logger.exception("后台任务 {} 失败", definition.name)
            self._finish(claimed.id, "failed", error=exc)
        else:
            self._finish(claimed.id, "succeeded")

    def _claim_next(self, queue_name: TaskQueue) -> ClaimedJob | None:
        now = datetime.now(timezone.utc)
        self._recover_expired_leases(now)
        return self._run_db(
            lambda db: BackgroundJobDAO(db).claim_next(queue_name.value, now)
        )

    def _recover_expired_leases(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        return self._run_db(
            lambda db: BackgroundJobDAO(db).recover_expired_leases(
                now, global_config.tasks.job_lease_seconds
            )
        )

    def _touch_running(self, job_id: str) -> bool:
        return self._run_db(
            lambda db: BackgroundJobDAO(db).touch_running(
                job_id, datetime.now(timezone.utc)
            )
        )

    def _finish(self, job_id: str, status: str, *, error: Exception | None = None) -> None:
        self._run_db(lambda db: BackgroundJobDAO(db).finish(job_id, status, error=error))

    def _schedule_retry(
        self, job_id: str, error: Exception, next_attempt_at: datetime
    ) -> None:
        self._run_db(
            lambda db: BackgroundJobDAO(db).schedule_retry(
                job_id, error, next_attempt_at
            )
        )

    def _fail_unrecoverable(self, job_id: str, error_type: str, message: str) -> None:
        self._run_db(
            lambda db: BackgroundJobDAO(db).fail_unrecoverable(
                job_id, error_type, message
            )
        )


def _encode_envelope(payload: Any, reference: TaskReference) -> str:
    envelope = {
        "version": 1,
        "payload": payload,
        "reference": {
            "resource_type": reference.resource_type,
            "resource_id": reference.resource_id,
            "request_id": reference.request_id,
            "metadata": reference.metadata,
        },
    }
    try:
        return json.dumps(envelope, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TaskPayloadError("任务 payload 与 reference.metadata 必须可 JSON 序列化") from exc


def _decode_payload(metadata_json: str) -> Any:
    try:
        envelope = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise TaskPayloadError("持久化任务 payload 不是有效 JSON") from exc
    if not isinstance(envelope, dict) or envelope.get("version") != 1 or "payload" not in envelope:
        raise TaskPayloadError("持久化任务 payload 格式不受当前运行时支持")
    return envelope["payload"]
