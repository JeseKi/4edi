"""受控执行 HTTP 短数据库事务的基础设施。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, fields, is_dataclass
from threading import Lock
from time import perf_counter
from typing import Any, Protocol, TypeVar

from fastapi import Request
from loguru import logger
from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session

_Result = TypeVar("_Result")


class DatabaseExecutorRunner(Protocol):
    """审计等组件所需的最小数据库执行器接口。"""

    async def run(self, operation: Callable[[Session], _Result]) -> _Result: ...


class DatabaseExecutorOverloadedError(RuntimeError):
    """数据库执行槽位在规定时间内不可用。"""


class UnsafeDatabaseResultError(TypeError):
    """数据库回调试图将 Session 或 ORM 实体带出事务。"""


@dataclass(frozen=True)
class DatabaseExecutorStats:
    """供日志和未来监控读取的进程内执行器统计快照。"""

    active: int
    waiting: int
    completed: int
    failed: int
    queue_timeouts: int
    total_queue_wait_seconds: float
    total_execution_seconds: float


class DatabaseExecutor:
    """在线程池中执行完整、短生命周期的同步 SQLAlchemy 事务。"""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        dialect: str,
        max_workers: int,
        queue_timeout_seconds: float,
        statement_timeout_seconds: int | None = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("DatabaseExecutor 的 max_workers 必须至少为 1")
        if queue_timeout_seconds <= 0:
            raise ValueError("DatabaseExecutor 的队列超时必须大于 0")
        if statement_timeout_seconds is not None and statement_timeout_seconds < 1:
            raise ValueError("DatabaseExecutor 的 SQL 超时必须至少为 1 秒")

        self._session_factory = session_factory
        self._dialect = dialect
        self.max_workers = max_workers
        self.queue_timeout_seconds = queue_timeout_seconds
        self.statement_timeout_seconds = statement_timeout_seconds
        self._slots = asyncio.Semaphore(max_workers)
        self._thread_pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="template-database",
        )
        self._closed = False
        self._stats_lock = Lock()
        self._active = 0
        self._waiting = 0
        self._completed = 0
        self._failed = 0
        self._queue_timeouts = 0
        self._total_queue_wait_seconds = 0.0
        self._total_execution_seconds = 0.0

    async def run(self, operation: Callable[[Session], _Result]) -> _Result:
        """排队后运行一个短事务；取消请求不会提前释放执行槽位。"""
        if self._closed:
            raise RuntimeError("DatabaseExecutor 已关闭")

        queued_at = perf_counter()
        self._change_stats(waiting=1)
        try:
            await asyncio.wait_for(
                self._slots.acquire(), timeout=self.queue_timeout_seconds
            )
        except TimeoutError as exc:
            self._change_stats(waiting=-1, queue_timeouts=1)
            logger.warning(
                "数据库执行器排队超时: timeout_seconds={}",
                self.queue_timeout_seconds,
            )
            raise DatabaseExecutorOverloadedError("数据库繁忙，请稍后重试") from exc
        except BaseException:
            self._change_stats(waiting=-1)
            raise

        queue_wait_seconds = perf_counter() - queued_at
        self._change_stats(
            waiting=-1,
            active=1,
            total_queue_wait_seconds=queue_wait_seconds,
        )
        if self._closed:
            self._slots.release()
            self._change_stats(active=-1)
            raise RuntimeError("DatabaseExecutor 已关闭")

        loop = asyncio.get_running_loop()
        try:
            future = loop.run_in_executor(self._thread_pool, self._run_operation, operation)
        except BaseException:
            self._slots.release()
            self._change_stats(active=-1)
            raise

        def _release_slot(_: asyncio.Future[_Result]) -> None:
            self._slots.release()
            self._change_stats(active=-1)

        future.add_done_callback(_release_slot)
        # shield 确保 HTTP 请求取消时，同步回调仍完整收尾、关闭 Session 后才释放槽位。
        return await asyncio.shield(future)

    async def shutdown(self) -> None:
        """停止接收新任务，并取消尚未开始的线程池工作。"""
        self._closed = True
        self._thread_pool.shutdown(wait=False, cancel_futures=True)

    def snapshot(self) -> DatabaseExecutorStats:
        """返回统计快照，不暴露可变内部状态。"""
        with self._stats_lock:
            return DatabaseExecutorStats(
                active=self._active,
                waiting=self._waiting,
                completed=self._completed,
                failed=self._failed,
                queue_timeouts=self._queue_timeouts,
                total_queue_wait_seconds=self._total_queue_wait_seconds,
                total_execution_seconds=self._total_execution_seconds,
            )

    def _run_operation(self, operation: Callable[[Session], _Result]) -> _Result:
        started_at = perf_counter()
        db = self._session_factory()
        try:
            if self._dialect == "postgresql" and self.statement_timeout_seconds is not None:
                milliseconds = self.statement_timeout_seconds * 1000
                db.execute(text(f"SET LOCAL statement_timeout = {milliseconds}"))
            result = operation(db)
            _assert_safe_database_result(result)
            db.commit()
            self._change_stats(completed=1)
            return result
        except BaseException:
            db.rollback()
            self._change_stats(failed=1)
            raise
        finally:
            self._change_stats(total_execution_seconds=perf_counter() - started_at)
            db.close()

    def _change_stats(
        self,
        *,
        active: int = 0,
        waiting: int = 0,
        completed: int = 0,
        failed: int = 0,
        queue_timeouts: int = 0,
        total_queue_wait_seconds: float = 0.0,
        total_execution_seconds: float = 0.0,
    ) -> None:
        with self._stats_lock:
            self._active += active
            self._waiting += waiting
            self._completed += completed
            self._failed += failed
            self._queue_timeouts += queue_timeouts
            self._total_queue_wait_seconds += total_queue_wait_seconds
            self._total_execution_seconds += total_execution_seconds


def get_database_executor(request: Request) -> DatabaseExecutor:
    """FastAPI 依赖：获取当前 Web 应用的数据库执行器。"""
    return request.app.state.runtime.database_executor


def _assert_safe_database_result(value: Any, *, seen: set[int] | None = None) -> None:
    """递归阻止 ORM 实体和 Session 越过受控事务边界。"""
    if isinstance(value, Session):
        raise UnsafeDatabaseResultError("数据库回调不能返回 Session")

    if sa_inspect(value, raiseerr=False) is not None:
        raise UnsafeDatabaseResultError("数据库回调不能返回 ORM 实体")

    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return

    seen = seen or set()
    value_id = id(value)
    if value_id in seen:
        return
    seen.add(value_id)

    if isinstance(value, Mapping):
        for nested in value.values():
            _assert_safe_database_result(nested, seen=seen)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            _assert_safe_database_result(nested, seen=seen)
        return
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _assert_safe_database_result(getattr(value, field.name), seen=seen)
