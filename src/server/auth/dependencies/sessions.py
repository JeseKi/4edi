# -*- coding: utf-8 -*-
"""认证依赖会话类型。"""

from dataclasses import dataclass

@dataclass(frozen=True)
class CurrentRefreshSession:
    """离开数据库事务后仍可安全使用的 refresh-session 快照。"""

    user_id: int
    username: str
    role: str
    refresh_jti: str
    payload: dict
