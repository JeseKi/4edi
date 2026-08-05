"""模板级任务定义注册表。

Web 发布端与 worker 必须从这里获得完全相同的任务定义，避免一端可入队、
另一端未注册 handler 的配置漂移。
"""

from __future__ import annotations

from src.server.config import global_config
from src.server.platform.features import resolve_features, task_definitions_for

from .runtime import TaskDefinition


def get_task_definitions() -> tuple[TaskDefinition, ...]:
    """从与 Web 相同的功能目录取得 worker 任务定义。"""
    features = resolve_features(
        global_config.app.enabled_features, app_env=global_config.app.env
    )
    return task_definitions_for(features)
