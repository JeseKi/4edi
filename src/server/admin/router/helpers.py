# -*- coding: utf-8 -*-
"""管理员用户路由的审计快照辅助函数。"""

from src.server.auth.models import User


def user_snapshot(user: User) -> dict[str, object]:
    return {
        "username": user.username,
        "name": user.name,
        "role": user.role.value,
        "status": user.status.value,
        "scope_overrides": list(user.scope_overrides_list or ()),
    }


def changed_values(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    changed_fields = [key for key, value in after.items() if before.get(key) != value]
    return {
        "changed_fields": changed_fields,
        "before": {key: before[key] for key in changed_fields},
        "after": {key: after[key] for key in changed_fields},
    }
