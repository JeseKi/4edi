# -*- coding: utf-8 -*-
"""本地模拟支付通道，用于开发与测试。"""

from __future__ import annotations


from .base import PaymentProvider, PrepayResult, QueryResult, RefundResult


class MockPaymentProvider(PaymentProvider):
    """模拟微信支付：统一下单返回假二维码地址，支付由 mock-pay 接口直接完成。"""

    key = "wechat"
    implementation = "mock"

    def is_configured(self) -> bool:
        return True

    def create_prepay(
        self,
        *,
        out_trade_no: str,
        amount_fen: int,
        description: str,
        pay_type: str,
        notify_url: str,
    ) -> PrepayResult:
        return PrepayResult(
            code_url=f"weixin://wxpay/bizpayurl?pr={out_trade_no}",
            prepay_id=f"mock-prepay-{out_trade_no}",
        )

    def query_order(self, *, out_trade_no: str) -> QueryResult:
        return QueryResult(paid=False)

    def verify_notification(self, headers: dict, body: bytes) -> dict | None:
        return None

    def create_refund(
        self,
        *,
        out_refund_no: str,
        out_trade_no: str,
        amount_fen: int,
        total_fen: int,
        description: str,
    ) -> RefundResult:
        del out_trade_no, amount_fen, total_fen, description
        return RefundResult(
            success=True, refund_id=f"mock-refund-{out_refund_no}"
        )
