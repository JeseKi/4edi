"""应用进程的类型化运行时容器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.server.config import GlobalConfig

if TYPE_CHECKING:
    from src.server.audit.runtime import AuditRuntime
    from src.server.database_executor import DatabaseExecutor
    from src.server.mail.runtime import MailDeliveryExecutor
    from src.server.task_runtime.runtime import TaskRuntime


@dataclass
class ApplicationRuntime:
    """组合根创建的进程级服务，业务模块不负责构造其中任何一项。"""

    settings: GlobalConfig
    enabled_features: frozenset[str]
    database_executor: DatabaseExecutor
    mail_delivery_executor: MailDeliveryExecutor
    task_runtime: TaskRuntime
    audit_runtime: AuditRuntime | None = None
