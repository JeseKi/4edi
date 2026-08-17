# -*- coding: utf-8 -*-
"""腾讯云短信验证码发送服务。"""

from __future__ import annotations

import re

from fastapi import HTTPException, status
from loguru import logger

from src.server.auth.sms_config import sms_config
from src.server.config import global_config

MAINLAND_PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


def normalize_mainland_phone(phone: str) -> str:
    """将中国大陆手机号规范化为 11 位数字。"""
    normalized = re.sub(r"[\s-]+", "", phone.strip())
    if normalized.startswith("+86"):
        normalized = normalized[3:]
    elif normalized.startswith("0086"):
        normalized = normalized[4:]
    elif normalized.startswith("86") and len(normalized) == 13:
        normalized = normalized[2:]

    if not MAINLAND_PHONE_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号格式不正确",
        )
    return normalized


def to_tencent_phone_number(phone: str) -> str:
    """腾讯云短信要求 E.164 格式。"""
    return f"+86{normalize_mainland_phone(phone)}"


def is_tencent_sms_configured() -> bool:
    return all(
        [
            sms_config.secret_id.strip(),
            sms_config.secret_key.strip(),
            sms_config.sdk_app_id.strip(),
            sms_config.sign_name.strip(),
            sms_config.template_id.strip(),
        ]
    )


def send_tencent_sms_verification_code(
    phone: str, code: str, *, expires_minutes: int
) -> None:
    """通过腾讯云短信发送验证码。"""
    if not is_tencent_sms_configured():
        raise RuntimeError("腾讯云短信配置不完整")

    try:
        from tencentcloud.common import credential  # type: ignore[import-not-found, import-untyped]
        from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException  # type: ignore[import-not-found, import-untyped]
        from tencentcloud.common.profile.client_profile import ClientProfile  # type: ignore[import-not-found, import-untyped]
        from tencentcloud.common.profile.http_profile import HttpProfile  # type: ignore[import-not-found, import-untyped]
        from tencentcloud.sms.v20210111 import models, sms_client  # type: ignore[import-not-found, import-untyped]
    except ImportError as exc:
        raise RuntimeError("未安装腾讯云短信 SDK") from exc

    try:
        cred = credential.Credential(
            sms_config.secret_id.strip(),
            sms_config.secret_key.strip(),
        )
        http_profile = HttpProfile()
        http_profile.endpoint = sms_config.endpoint.strip() or "sms.tencentcloudapi.com"
        http_profile.reqTimeout = max(1, sms_config.timeout_seconds)

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        client = sms_client.SmsClient(
            cred, sms_config.region.strip(), client_profile
        )
        request = models.SendSmsRequest()
        request.SmsSdkAppId = sms_config.sdk_app_id.strip()
        request.SignName = sms_config.sign_name.strip()
        request.TemplateId = sms_config.template_id.strip()
        request.TemplateParamSet = [code, str(expires_minutes)]
        request.PhoneNumberSet = [to_tencent_phone_number(phone)]

        response = client.SendSms(request)
    except TencentCloudSDKException as exc:
        logger.error("腾讯云短信发送异常：{error}", error=exc)
        raise RuntimeError("腾讯云短信发送失败") from exc

    statuses = getattr(response, "SendStatusSet", None)
    if not statuses:
        logger.error("腾讯云短信响应缺少 SendStatusSet")
        raise RuntimeError("腾讯云短信响应无效")

    first_status = statuses[0]
    code_value = getattr(first_status, "Code", "")
    message = getattr(first_status, "Message", "")
    if code_value != "Ok":
        logger.error(
            "腾讯云短信发送失败 code={code}, message={message}",
            code=code_value,
            message=message,
        )
        raise RuntimeError(message or "腾讯云短信发送失败")


def deliver_phone_verification_code(phone: str, code: str, expires_minutes: int) -> None:
    """发送手机验证码；未配置腾讯云短信时在开发/测试环境打印到日志。"""
    if not is_tencent_sms_configured():
        if global_config.app.env not in {"dev", "test"}:
            raise RuntimeError("短信服务未配置，请联系管理员")
        logger.warning("腾讯云短信未配置，验证码将打印到控制台中")
        logger.warning(f"手机号 {phone} 的验证码：{code}")
        return
    send_tencent_sms_verification_code(phone, code, expires_minutes=expires_minutes)
