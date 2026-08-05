"""持久化任务 worker 的独立进程入口。"""

from __future__ import annotations

import asyncio
import signal

from loguru import logger

from src.server.database import create_task_database_runtime, run_in_session_factory
from src.server.logging_config import setup_logging

from .registry import get_task_definitions
from .runtime import TaskRuntime


async def _run_worker() -> None:
    setup_logging(process_role="worker")
    database_runtime = create_task_database_runtime()
    runtime = TaskRuntime(
        definitions=get_task_definitions(),
        session_runner=lambda operation: run_in_session_factory(
            database_runtime.session_factory, operation
        ),
        sqlite_single_worker=database_runtime.is_sqlite,
    )
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        logger.info("worker 收到停止信号，不再领取新任务")
        stopped.set()

    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, request_stop)
        except NotImplementedError:  # pragma: no cover - Windows fallback
            signal.signal(signal_name, lambda *_args: request_stop())

    await runtime.start()
    logger.success("后台任务 worker 已启动")
    try:
        await stopped.wait()
    finally:
        await runtime.stop()
        database_runtime.dispose()
        logger.info("后台任务 worker 已停止")


def main() -> None:
    asyncio.run(_run_worker())


if __name__ == "__main__":
    main()
