"""受控执行同步邮件投递的运行时基础设施。"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TypeVar

from loguru import logger

_Result = TypeVar("_Result")


class MailDeliveryOverloadedError(Exception):
    """邮件投递槽位在规定时间内不可用。"""


class MailDeliveryExecutor:
    """在线程池中执行同步 SMTP 操作，并限制每个 Web 进程的并发投递数。"""

    def __init__(self, *, max_workers: int, queue_timeout_seconds: float) -> None:
        if max_workers < 1:
            raise ValueError("MailDeliveryExecutor 的 max_workers 必须至少为 1")
        if queue_timeout_seconds <= 0:
            raise ValueError("MailDeliveryExecutor 的队列超时必须大于 0")

        self.max_workers = max_workers
        self.queue_timeout_seconds = queue_timeout_seconds
        self._slots = asyncio.Semaphore(max_workers)
        self._thread_pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="template-mail",
        )
        self._closed = False

    async def run(
        self, operation: Callable[..., _Result], /, *args: object, **kwargs: object
    ) -> _Result:
        """排队执行同步投递；取消 HTTP 请求不会中断已开始的 SMTP 操作。"""
        if self._closed:
            raise RuntimeError("MailDeliveryExecutor 已关闭")

        try:
            await asyncio.wait_for(
                self._slots.acquire(), timeout=self.queue_timeout_seconds
            )
        except TimeoutError as exc:
            logger.warning(
                "邮件投递执行器排队超时: timeout_seconds={}",
                self.queue_timeout_seconds,
            )
            raise MailDeliveryOverloadedError("邮件发送繁忙，请稍后重试") from exc

        if self._closed:
            self._slots.release()
            raise RuntimeError("MailDeliveryExecutor 已关闭")

        loop = asyncio.get_running_loop()
        try:
            future = loop.run_in_executor(
                self._thread_pool, partial(operation, *args, **kwargs)
            )
        except BaseException:
            self._slots.release()
            raise

        future.add_done_callback(lambda _: self._slots.release())
        return await asyncio.shield(future)

    async def shutdown(self) -> None:
        """停止接收新任务，并取消尚未开始的投递。"""
        self._closed = True
        self._thread_pool.shutdown(wait=False, cancel_futures=True)
