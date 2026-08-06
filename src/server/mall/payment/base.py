# -*- coding: utf-8 -*-
"""支付 Provider 抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PaymentMode = Literal["real", "mock"]


@dataclass(frozen=True)
class PrepayResult:
    """统一下单返回的支付凭证。"""

    code_url: str | None = None
    prepay_id: str | None = None
    jsapi_params: dict | None = None


@dataclass(frozen=True)
class QueryResult:
    """订单查询结果。"""

    paid: bool
    transaction_id: str | None = None
    paid_at: datetime | None = None
    raw: dict | None = None


class PaymentProvider(ABC):
    """可替换的支付通道实现；mock 与真实微信支付共用该契约。"""

    key: str
    implementation: PaymentMode

    @property
    def is_mock(self) -> bool:
        return self.implementation == "mock"

    @abstractmethod
    def is_configured(self) -> bool:
        """是否具备发起真实支付所需配置。"""

    @abstractmethod
    def create_prepay(
        self,
        *,
        out_trade_no: str,
        amount_fen: int,
        description: str,
        pay_type: str,
        notify_url: str,
    ) -> PrepayResult:
        """发起统一下单，返回支付凭证。"""

    @abstractmethod
    def query_order(self, *, out_trade_no: str) -> QueryResult:
        """查询商户订单在支付通道侧的状态。"""

    @abstractmethod
    def verify_notification(self, headers: dict, body: bytes) -> dict | None:
        """验签并解密支付结果通知；无效通知返回 None。"""

    def health_check(self) -> dict:
        configured = self.is_configured()
        return {
            "provider": self.key,
            "implementation": self.implementation,
            "ok": configured,
            "message": "provider is not configured" if not configured else "ok",
        }
