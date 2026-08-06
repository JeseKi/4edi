# -*- coding: utf-8 -*-
"""支付 Provider 边界：真实微信支付与本地模拟实现。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .service import get_payment_provider

__all__ = ["get_payment_provider"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import service

        return getattr(service, name)
    raise AttributeError(name)
