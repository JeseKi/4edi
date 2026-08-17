# -*- coding: utf-8 -*-
"""微信支付（APIv3）实现。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cryptography import x509
from loguru import logger

from .base import PaymentProvider, PrepayResult, QueryResult, RefundResult


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
    """基于 wechatpayv3 库的微信支付直连商户实现。"""

    key = "wechat"
    implementation = "real"

    def __init__(
        self,
        *,
        app_id: str,
        merchant_id: str,
        private_key_path: str,
        merchant_cert_path: str,
        platform_cert_dir: str,
        cert_serial_no: str,
        apiv3_key: str,
        public_key_path: str = "",
        public_key_id: str = "",
        notify_url: str = "",
    ) -> None:
        self._app_id = app_id
        self._merchant_id = merchant_id
        self._private_key_path = private_key_path
        self._merchant_cert_path = merchant_cert_path
        self._platform_cert_dir = platform_cert_dir
        self._public_key_path = public_key_path
        self._public_key_id = public_key_id
        self._cert_serial_no = cert_serial_no
        self._apiv3_key = apiv3_key
        self._notify_url = notify_url
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        from wechatpayv3 import WeChatPay, WeChatPayType  # type: ignore[import-untyped]

        private_key_path = Path(self._private_key_path)
        private_key = private_key_path.read_text(encoding="utf-8")
        public_key = None
        if self._public_key_path:
            public_key = Path(self._public_key_path).read_text(encoding="utf-8")
        platform_cert_dir = (
            Path(self._platform_cert_dir)
            if self._platform_cert_dir
            else self._merchant_cert_path_for_serial().parent / "platform"
        )
        platform_cert_dir.mkdir(parents=True, exist_ok=True)
        self._client = WeChatPay(
            wechatpay_type=WeChatPayType.NATIVE,
            mchid=self._merchant_id,
            private_key=private_key,
            cert_serial_no=self._resolved_cert_serial_no(),
            appid=self._app_id,
            apiv3_key=self._apiv3_key,
            notify_url=self._notify_url,
            cert_dir=str(platform_cert_dir),
            public_key=public_key,
            public_key_id=self._public_key_id or None,
        )
        return self._client

    def _merchant_cert_path_for_serial(self) -> Path:
        if self._merchant_cert_path:
            return Path(self._merchant_cert_path)
        return Path(self._private_key_path).with_name("apiclient_cert.pem")

    def _resolved_cert_serial_no(self) -> str:
        if self._cert_serial_no:
            return self._cert_serial_no
        cert_path = self._merchant_cert_path_for_serial()
        if not cert_path.is_file():
            return ""
        try:
            certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
        except (OSError, ValueError):
            return ""
        return format(certificate.serial_number, "X")

    def is_configured(self) -> bool:
        return bool(
            self._app_id
            and self._merchant_id
            and self._private_key_path
            and Path(self._private_key_path).is_file()
            and self._resolved_cert_serial_no()
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
        expires_at: datetime,
    ) -> PrepayResult:
        from wechatpayv3 import WeChatPayType

        if pay_type != "native":
            raise RuntimeError("当前仅支持微信 Native 扫码支付")
        client = self._get_client()
        code, message = client.pay(
            description=description,
            out_trade_no=out_trade_no,
            amount={"total": amount_fen, "currency": "CNY"},
            notify_url=notify_url,
            time_expire=expires_at.isoformat(timespec="seconds"),
            pay_type=WeChatPayType.NATIVE,
        )
        if code != 200:
            logger.error("微信支付统一下单失败：{} {}", code, message)
            raise RuntimeError(f"微信支付统一下单失败：{code}")
        result = _parse_body(message)
        code_url = result.get("code_url")
        if not code_url:
            raise RuntimeError("微信支付未返回二维码地址")
        return PrepayResult(code_url=code_url)

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

    def close_order(self, *, out_trade_no: str) -> None:
        client = self._get_client()
        code, message = client.close(out_trade_no=out_trade_no)
        if code not in {200, 204}:
            logger.warning("微信支付关闭订单失败：{} {}", code, message)

    def create_refund(
        self,
        *,
        out_refund_no: str,
        out_trade_no: str,
        amount_fen: int,
        total_fen: int,
        description: str,
    ) -> RefundResult:
        client = self._get_client()
        code, message = client.refund(
            out_refund_no=out_refund_no,
            out_trade_no=out_trade_no,
            amount={"refund": amount_fen, "total": total_fen, "currency": "CNY"},
            reason=description,
        )
        if code != 200:
            logger.error("微信退款申请失败：{} {}", code, message)
            return RefundResult(success=False, message=f"微信退款申请失败：{code}")
        result = _parse_body(message)
        return RefundResult(
            success=True,
            refund_id=result.get("refund_id"),
            message=str(message),
        )

    def configuration_error(self) -> str | None:
        missing = []
        if not self._app_id:
            missing.append("WECHAT_PAY_APP_ID")
        if not self._merchant_id:
            missing.append("WECHAT_PAY_MERCHANT_ID")
        if not self._private_key_path or not Path(self._private_key_path).is_file():
            missing.append("WECHAT_PAY_PRIVATE_KEY_PATH")
        if not self._resolved_cert_serial_no():
            missing.append("商户证书序列号（WECHAT_PAY_CERT_SERIAL_NO 或 apiclient_cert.pem）")
        if not self._apiv3_key:
            missing.append("WECHAT_PAY_APIV3_KEY")
        if bool(self._public_key_path) != bool(self._public_key_id):
            missing.append("WECHAT_PAY_PUBLIC_KEY_PATH 与 WECHAT_PAY_PUBLIC_KEY_ID")
        elif self._public_key_path and not Path(self._public_key_path).is_file():
            missing.append("WECHAT_PAY_PUBLIC_KEY_PATH")
        if not self._notify_url:
            missing.append("WECHAT_PAY_NOTIFY_BASE_URL 或 APP_DOMAIN")
        if not missing:
            return None
        return f"微信支付配置不完整：{', '.join(missing)}"
