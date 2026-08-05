# -*- coding: utf-8 -*-
"""OAuth Provider 路由包。"""

from fastapi import APIRouter
from fastapi.security import HTTPBearer

router = APIRouter(prefix="/api/oauth-provider", tags=["OAuth Provider"])
bearer_scheme = HTTPBearer(auto_error=True)

from . import authorization as _authorization  # noqa: F401,E402
from . import clients as _clients  # noqa: F401,E402
from . import tokens as _tokens  # noqa: F401,E402

__all__ = ["router"]
