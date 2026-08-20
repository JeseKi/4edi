# -*- coding: utf-8 -*-
"""用户投诉路由测试：提交、登录校验、字段校验。"""

from __future__ import annotations

from src.server.auth.tests._auth_router_helpers import _register_user

VALID_PAYLOAD = {
    "subject": "不良信息发布投诉",
    "content": "该信息涉嫌虚假宣传，请核实处理。",
    "contact": "13800001111",
}


def _login(test_client, *, username: str, password: str = "Password123"):
    resp = test_client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_submit_requires_login(test_client):
    resp = test_client.post("/api/complaint", json=VALID_PAYLOAD)
    assert resp.status_code == 401


def test_submit_missing_fields(test_client):
    _register_user(test_client, username="bob-cmpl", email="bob-cmpl@example.com")
    headers = _login(test_client, username="bob-cmpl")

    # Pydantic 校验失败返回 422
    resp = test_client.post("/api/complaint", headers=headers, json={})
    assert resp.status_code == 422, resp.text

    resp = test_client.post(
        "/api/complaint", headers=headers, json={"subject": "   ", "content": "x"}
    )
    assert resp.status_code == 422, resp.text


def test_submit_success(test_client):
    _register_user(test_client, username="carol-cmpl", email="carol-cmpl@example.com")
    headers = _login(test_client, username="carol-cmpl")

    resp = test_client.post("/api/complaint", headers=headers, json=VALID_PAYLOAD)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["subject"] == VALID_PAYLOAD["subject"]
    assert body["content"] == VALID_PAYLOAD["content"]
    assert body["contact"] == VALID_PAYLOAD["contact"]
    assert body["status"] == "pending"
    assert "created_at" in body

    # 不传可选联系方式也应成功
    resp = test_client.post(
        "/api/complaint",
        headers=headers,
        json={"subject": "另一条投诉", "content": "同样需要核实。"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["contact"] is None
