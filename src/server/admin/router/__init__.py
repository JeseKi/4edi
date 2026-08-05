# -*- coding: utf-8 -*-
"""管理员用户管理路由包。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["管理员"])

# Import route modules so their decorators register endpoints on ``router``.
from . import collection as _collection  # noqa: F401,E402
from . import user_detail as _user_detail  # noqa: F401,E402

__all__ = ["router"]
