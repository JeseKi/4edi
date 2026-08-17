# -*- coding: utf-8 -*-
"""支付 Provider 选择服务。"""

from __future__ import annotations

from src.server.mall.config import mall_config

from .base import PaymentProvider
from .mock import MockPaymentProvider
from .wechat_v3 import WeChatPayV3Provider


def get_payment_provider() -> PaymentProvider:
    """按配置返回真实微信支付或本地模拟实现。"""
    if mall_config.payment_mode == "real":
        return WeChatPayV3Provider(
            app_id=mall_config.wechat_pay_app_id,
            merchant_id=mall_config.wechat_pay_merchant_id,
            private_key_path=mall_config.wechat_pay_private_key_path,
            merchant_cert_path=mall_config.wechat_pay_merchant_cert_path,
            platform_cert_dir=mall_config.wechat_pay_platform_cert_dir,
            public_key_path=mall_config.wechat_pay_public_key_path,
            public_key_id=mall_config.wechat_pay_public_key_id,
            cert_serial_no=mall_config.wechat_pay_cert_serial_no,
            apiv3_key=mall_config.wechat_pay_apiv3_key,
            notify_url=_resolve_notify_url(),
        )
    return MockPaymentProvider()


def _resolve_notify_url() -> str:
    base = mall_config.wechat_pay_notify_base_url or mall_config_wechat_domain()
    if not base:
        return ""
    return f"{base.rstrip('/')}/api/mall/payments/wechat/notify"


def mall_config_wechat_domain() -> str:
    from src.server.config import global_config

    return global_config.app.domain
