# -*- coding: utf-8 -*-
"""真实微信支付（APIv3）实现。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from .base import PaymentProvider, PrepayResult, QueryResult


def _parse_wechat_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed
    except ValueError:
        return None


def _parse_body(message: str | bytes | dict) -> dict:
    if isinstance(message, dict):
        return message
    if isinstance(message, bytes):
        try:
            return json.loads(message.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    try:
        return json.loads(message)
    except (TypeError, json.JSONDecodeError):
        return {}


class WeChatPayV3Provider(PaymentProvider):
    """基于 wechatpayv3 库的真实微信支付直连商户实现。"""

    key = "wechat"
    implementation = "real"

    def __init__(
        self,
        *,
        app_id: str,
        merchant_id: str,
        private_key_path: str,
        cert_serial_no: str,
        apiv3_key: str,
        notify_url: str = "",
    ) -> None:
        self._app_id = app_id
        self._merchant_id = merchant_id
        self._private_key_path = private_key_path
        self._cert_serial_no = cert_serial_no
        self._apiv3_key = apiv3_key
        self._notify_url = notify_url
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        from wechatpayv3 import WeChatPay, WeChatPayType  # type: ignore[import-untyped]

        private_key = Path(self._private_key_path).read_text(encoding="utf-8")
        self._client = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=self._merchant_id,
            private_key=private_key,
            cert_serial_no=self._cert_serial_no,
            appid=self._app_id,
            apiv3_key=self._apiv3_key,
            notify_url=self._notify_url,
        )
        return self._client

    def is_configured(self) -> bool:
        return bool(
            self._app_id
            and self._merchant_id
            and self._private_key_path
            and Path(self._private_key_path).is_file()
            and self._cert_serial_no
            and self._apiv3_key
        )

    def create_prepay(
        self,
        *,
        out_trade_no: str,
        amount_fen: int,
        description: str,
        pay_type: str,
        notify_url: str,
    ) -> PrepayResult:
        from wechatpayv3 import WeChatPayType

        client = self._get_client()
        code, message = client.pay(
            description=description,
            out_trade_no=out_trade_no,
            amount={"total": amount_fen, "currency": "CNY"},
            notify_url=notify_url,
            pay_type=WeChatPayType.NATIVE if pay_type == "native" else WeChatPayType.JSAPI,
        )
        if code != 200:
            logger.error("微信支付统一下单失败：{} {}", code, message)
            raise RuntimeError(f"微信支付统一下单失败：{code}")
        result = _parse_body(message)
        code_url = result.get("code_url")
        if code_url:
            return PrepayResult(code_url=code_url)
        return PrepayResult(prepay_id=result.get("prepay_id"))

    def query_order(self, *, out_trade_no: str) -> QueryResult:
        client = self._get_client()
        code, message = client.query(out_trade_no=out_trade_no)
        if code != 200:
            logger.error("微信支付订单查询失败：{} {}", code, message)
            return QueryResult(paid=False)
        result = _parse_body(message)
        trade_state = result.get("trade_state")
        return QueryResult(
            paid=trade_state == "SUCCESS",
            transaction_id=result.get("transaction_id"),
            paid_at=_parse_wechat_datetime(result.get("success_time")),
            raw=result,
        )

    def verify_notification(self, headers: dict, body: bytes) -> dict | None:
        client = self._get_client()
        try:
            return client.callback(headers=headers, body=body)
        except Exception as exc:
            logger.warning("微信支付通知验签失败：{}", exc)
            return None
