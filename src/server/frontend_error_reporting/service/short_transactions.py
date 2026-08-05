"""前端错误上报的短请求处理。"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from time import monotonic

from loguru import logger

from src.server.frontend_error_reporting.schemas import FrontendErrorReport


class FrontendErrorRateLimiter:
    """轻量级、进程内的每 IP 滑动窗口限流器。"""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client_ip: str, *, limit: int, window_seconds: float = 60) -> bool:
        now = monotonic()
        events = self._events[client_ip]
        cutoff = now - window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True

    def clear(self) -> None:
        self._events.clear()


def log_frontend_error_report(report: FrontendErrorReport, *, client_ip: str) -> None:
    """将已校验的浏览器报告作为单行 JSON 写入专属日志 sink。"""

    message = json.dumps(
        {"client_ip": client_ip, **report.model_dump(mode="json")},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    logger.bind(log_type="frontend", client_ip=client_ip).error(message)
