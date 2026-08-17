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


@dataclass(frozen=True)
class RefundResult:
    """退款申请结果。"""

    success: bool
    refund_id: str | None = None
    message: str = ""


class PaymentProvider(ABC):
    """支付服务契约；微信支付与本地开发测试实现共用该边界。"""

    key: str
    implementation: PaymentMode

    @property
    def is_mock(self) -> bool:
        return self.implementation == "mock"

    @abstractmethod
    def is_configured(self) -> bool:
        """是否具备发起微信支付所需配置。"""

    @abstractmethod
    def create_prepay(
        self,
        *,
        out_trade_no: str,
        amount_fen: int,
        description: str,
        pay_type: str,
        notify_url: str,
        expires_at: datetime,
    ) -> PrepayResult:
        """发起统一下单，返回支付凭证。"""

    @abstractmethod
    def query_order(self, *, out_trade_no: str) -> QueryResult:
        """查询商户订单在支付通道侧的状态。"""

    @abstractmethod
    def verify_notification(self, headers: dict, body: bytes) -> dict | None:
        """验签并解密支付结果通知；无效通知返回 None。"""

    @abstractmethod
    def close_order(self, *, out_trade_no: str) -> None:
        """关闭未支付交易；实现应保证重复调用安全。"""

    @abstractmethod
    def create_refund(
        self,
        *,
        out_refund_no: str,
        out_trade_no: str,
        amount_fen: int,
        total_fen: int,
        description: str,
    ) -> RefundResult:
        """发起退款申请；退款结果可能异步到达（通过退款回调确认）。"""

    def health_check(self) -> dict:
        configured = self.is_configured()
        return {
            "provider": self.key,
            "implementation": self.implementation,
            "ok": configured,
            "message": "provider is not configured" if not configured else "ok",
        }

    def configuration_error(self) -> str | None:
        if self.is_configured():
            return None
        return "支付通道配置不完整"
