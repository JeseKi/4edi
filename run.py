#!/usr/bin/env python
"""同容器 Web 与后台 worker 的进程监督入口。"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from time import monotonic, sleep

from loguru import logger

from src.server.logging_config import setup_logging
from src.server.config import global_config
from src.server.platform.features import resolve_features, task_definitions_for


def _shutdown_processes(
    processes: dict[str, subprocess.Popen[bytes]], timeout_seconds: int
) -> None:
    for process in processes.values():
        if process.poll() is None:
            process.terminate()

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        if all(process.poll() is not None for process in processes.values()):
            return
        sleep(0.1)

    for process in processes.values():
        if process.poll() is None:
            logger.warning("子进程在优雅停止窗口内未退出，强制终止：pid={}", process.pid)
            process.kill()
    for process in processes.values():
        process.wait()


def main() -> int:
    setup_logging(process_role="supervisor")
    timeout_seconds = global_config.tasks.shutdown_timeout_seconds
    environment = os.environ.copy()
    processes: dict[str, subprocess.Popen[bytes]] = {
        "web": subprocess.Popen([sys.executable, "-m", "src.server.web"], env=environment),
    }
    features = resolve_features(
        global_config.app.enabled_features, app_env=global_config.app.env
    )
    if task_definitions_for(features):
        processes["worker"] = subprocess.Popen(
            [sys.executable, "-m", "src.server.task_runtime.worker"], env=environment
        )
    stopping = False

    def request_stop(_signal_number: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    logger.success("Web 与后台 worker 已启动")

    try:
        while not stopping:
            for name, process in processes.items():
                return_code = process.poll()
                if return_code is not None:
                    logger.error("{} 子进程异常退出，退出码：{}", name, return_code)
                    _shutdown_processes(processes, timeout_seconds)
                    return return_code if return_code != 0 else 1
            sleep(0.1)
    finally:
        _shutdown_processes(processes, timeout_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
