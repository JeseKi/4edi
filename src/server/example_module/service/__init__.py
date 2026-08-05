# -*- coding: utf-8 -*-
"""示例模块服务包（模板版）。

请求侧的短事务逻辑位于 :mod:`.short_transactions`；由 worker 执行的长时
任务位于 :mod:`.long_tasks`。此处重新导出既有接口，方便模块内调用和既有
导入路径继续使用。
"""

from .long_tasks import EXAMPLE_ASYNC_TASK, _run_async_task
from .short_transactions import (
    create_async_task,
    create_item,
    fetch_external_status,
    get_async_task_detail,
    get_item,
    launch_async_task,
)

__all__ = [
    "EXAMPLE_ASYNC_TASK",
    "create_async_task",
    "create_item",
    "fetch_external_status",
    "get_async_task_detail",
    "get_item",
    "launch_async_task",
    "_run_async_task",
]
