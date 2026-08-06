# -*- coding: utf-8 -*-
"""手机号注册、登录与密码重置的端到端路由测试。"""

from src.server.auth import service
from src.server.auth.service import sms


def test_phone_register_login_and_reset_flow(test_client):
    phone = "13800138000"
    password = "PhonePass123"

    # 发送手机验证码
    resp = test_client.post(
        "/api/auth/send-phone-verification-code", json={"phone": phone}
    )
    assert resp.status_code == 200, resp.text

    code = service.verification_codes[phone]["code"]
    assert len(code) == 6

    # 手机号注册
    resp = test_client.post(
        "/api/auth/register-with-phone-code",
        json={"phone": phone, "code": code, "password": password},
    )
    assert resp.status_code == 201, resp.text
    profile = resp.json()
    assert profile["phone"] == phone
    assert profile["username"].startswith("user_")
    assert profile["email"].endswith("@phone.mall.site")

    # 用手机号登录
    resp = test_client.post(
        "/api/auth/login", json={"username": phone, "password": password}
    )
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()

    # 用生成的用户名登录
    resp = test_client.post(
        "/api/auth/login",
        json={"username": profile["username"], "password": password},
    )
    assert resp.status_code == 200, resp.text

    # 重复注册同一手机号应失败
    resp = test_client.post(
        "/api/auth/send-phone-verification-code", json={"phone": phone}
    )
    assert resp.status_code == 200, resp.text
    code2 = service.verification_codes[phone]["code"]
    resp = test_client.post(
        "/api/auth/register-with-phone-code",
        json={"phone": phone, "code": code2, "password": password},
    )
    assert resp.status_code == 400, resp.text
    assert "已绑定" in resp.json()["detail"]

    # 手机号重置密码
    resp = test_client.post(
        "/api/auth/forgot-password/phone-code", json={"phone": phone}
    )
    assert resp.status_code == 200, resp.text
    reset_code = service.verification_codes[phone]["code"]
    resp = test_client.post(
        "/api/auth/forgot-password/phone-reset",
        json={"phone": phone, "code": reset_code, "new_password": "NewPass456"},
    )
    assert resp.status_code == 200, resp.text

    resp = test_client.post(
        "/api/auth/login", json={"username": phone, "password": "NewPass456"}
    )
    assert resp.status_code == 200, resp.text

    resp = test_client.post(
        "/api/auth/login", json={"username": phone, "password": password}
    )
    assert resp.status_code == 401, resp.text


def test_phone_verification_code_validation(test_client):
    # 无效手机号
    resp = test_client.post(
        "/api/auth/send-phone-verification-code", json={"phone": "12345"}
    )
    assert resp.status_code == 400, resp.text

    # 带 +86 前缀可规范化
    resp = test_client.post(
        "/api/auth/send-phone-verification-code", json={"phone": "+86 139 1234 5678"}
    )
    assert resp.status_code == 200, resp.text
    assert service.verification_codes["13912345678"]

    # 错误验证码
    resp = test_client.post(
        "/api/auth/register-with-phone-code",
        json={"phone": "13912345678", "code": "000000", "password": "PhonePass123"},
    )
    assert resp.status_code == 400, resp.text


def test_phone_verification_code_cooldown(test_client):
    phone = "13712345678"
    resp = test_client.post(
        "/api/auth/send-phone-verification-code", json={"phone": phone}
    )
    assert resp.status_code == 200, resp.text

    resp = test_client.post(
        "/api/auth/send-phone-verification-code", json={"phone": phone}
    )
    assert resp.status_code == 429, resp.text


def test_phone_register_placeholder_email_unique(test_db_session):
    """两个不同手机号应生成不同的占位邮箱。"""
    email1 = service.create_phone_placeholder_email("13800138001")
    email2 = service.create_phone_placeholder_email("13800138002")
    assert email1 != email2


def test_normalize_mainland_phone():
    assert sms.normalize_mainland_phone("+8613800138000") == "13800138000"
    assert sms.normalize_mainland_phone("0086 138 0013 8000") == "13800138000"
    assert sms.normalize_mainland_phone("13800138000") == "13800138000"
