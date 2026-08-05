"""同步 SMTP 投递执行器的回归测试。"""

from __future__ import annotations

import asyncio
from threading import Event

from starlette.requests import Request

from src.server.mail.runtime import MailDeliveryExecutor, MailDeliveryOverloadedError


def test_mail_delivery_overload_is_not_a_runtime_error() -> None:
    """路由可继续将真实 SMTP 运行时失败映射为 500。"""
    assert not issubclass(MailDeliveryOverloadedError, RuntimeError)


def test_mail_delivery_overload_handler_returns_503() -> None:
    from src.server.main import mail_delivery_overloaded_handler

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/send-verification-code",
            "headers": [],
        }
    )
    response = asyncio.run(
        mail_delivery_overloaded_handler(request, MailDeliveryOverloadedError())
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"


def test_mail_delivery_does_not_block_event_loop() -> None:
    async def scenario() -> None:
        executor = MailDeliveryExecutor(max_workers=1, queue_timeout_seconds=1)
        started = Event()
        release = Event()

        def slow_smtp_operation() -> str:
            started.set()
            assert release.wait(1)
            return "sent"

        task = asyncio.create_task(executor.run(slow_smtp_operation))
        assert await asyncio.to_thread(started.wait, 1)

        progressed = asyncio.Event()
        asyncio.get_running_loop().call_later(0.01, progressed.set)
        await asyncio.wait_for(progressed.wait(), timeout=0.2)

        release.set()
        assert await task == "sent"
        await executor.shutdown()

    asyncio.run(scenario())


def test_mail_delivery_limits_smtp_concurrency() -> None:
    async def scenario() -> None:
        executor = MailDeliveryExecutor(max_workers=1, queue_timeout_seconds=1)
        first_started = Event()
        second_started = Event()
        release_first = Event()

        def first_operation() -> None:
            first_started.set()
            assert release_first.wait(1)

        def second_operation() -> None:
            second_started.set()

        first = asyncio.create_task(executor.run(first_operation))
        assert await asyncio.to_thread(first_started.wait, 1)
        second = asyncio.create_task(executor.run(second_operation))

        await asyncio.sleep(0.05)
        assert not second_started.is_set()

        release_first.set()
        await first
        await second
        await executor.shutdown()

    asyncio.run(scenario())
