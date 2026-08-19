# -*- coding: utf-8 -*-
"""信息发布端到端路由测试：发布、可见性、审核、置顶与删除。"""

from __future__ import annotations

from src.server.auth.tests._auth_router_helpers import _auth_headers, _register_user

VALID_PAYLOAD = {
    "category": "mini_program",
    "title": "小程序开发定制",
    "price": "电话咨询",
    "contact_name": "张三",
    "contact_phone": "18312345067",
    "content": "承接各类小程序开发与定制服务，支持电商、直播、预约等场景。",
    "attributes": {"dev_method": "原生开发", "secondary_dev": "是"},
}


def _login(test_client, *, username: str, password: str = "Password123"):
    resp = test_client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return _auth_headers(resp.json()["access_token"])


def _login_admin(test_client):
    resp = test_client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert resp.status_code == 200, resp.text
    return _auth_headers(resp.json()["access_token"])


def test_categories_and_empty_public_list(test_client):
    resp = test_client.get("/api/information/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert {item["name"] for item in data} == {"小程序开发", "APP开发", "软件开发", "网站建设"}

    resp = test_client.get("/api/information")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_publish_requires_login(test_client):
    resp = test_client.post("/api/information", json=VALID_PAYLOAD)
    assert resp.status_code == 401


def test_full_flow_publish_review_public_list_delete(test_client, init_test_database):
    _register_user(test_client, username="alice-info", email="alice-info@example.com")
    alice_headers = _login(test_client, username="alice-info")

    # 发布 → 待审核，本人返回完整号码
    resp = test_client.post("/api/information", headers=alice_headers, json=VALID_PAYLOAD)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    post_id = created["id"]
    assert created["status"] == "pending"
    assert created["contact_phone"] == "18312345067"
    assert created["category_name"] == "小程序开发"

    # 新的待审核信息不对外公开
    resp = test_client.get("/api/information")
    assert resp.json()["total"] == 0

    resp = test_client.get(f"/api/information/{post_id}")
    assert resp.status_code == 404

    _register_user(test_client, username="bob-info", email="bob-info@example.com")
    bob_headers = _login(test_client, username="bob-info")

    # 非本人删除 → 403
    resp = test_client.delete(f"/api/information/{post_id}", headers=bob_headers)
    assert resp.status_code == 403

    # 管理员审核通过
    admin_headers = _login_admin(test_client)
    resp = test_client.post(
        f"/api/information/admin/posts/{post_id}/review",
        headers=admin_headers,
        json={"approved": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    # 公开列表与详情（手机号打码）
    resp = test_client.get("/api/information?category=mini_program")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert "contact_phone" not in body["items"][0]

    resp = test_client.get(f"/api/information/{post_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["contact_phone"] == "183****5067"
    assert detail["view_count"] == 1

    # 我的发布：完整号码 + 状态
    resp = test_client.get("/api/information/mine", headers=alice_headers)
    assert resp.status_code == 200
    mine = resp.json()
    assert len(mine) == 1
    assert mine[0]["status"] == "approved"
    assert mine[0]["contact_phone"] == "18312345067"

    # 管理员列表与置顶
    resp = test_client.get("/api/information/admin/posts?status=approved", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    resp = test_client.post(
        f"/api/information/admin/posts/{post_id}/top?on=true", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["is_top"] is True

    # 发布者删除后从公开列表消失
    resp = test_client.delete(f"/api/information/{post_id}", headers=alice_headers)
    assert resp.status_code == 200
    resp = test_client.get("/api/information")
    assert resp.json()["total"] == 0


def test_admin_reject_requires_reason(test_client, init_test_database):
    _register_user(test_client, username="carol-info", email="carol-info@example.com")
    headers = _login(test_client, username="carol-info")

    resp = test_client.post("/api/information", headers=headers, json=VALID_PAYLOAD)
    assert resp.status_code == 201, resp.text
    post_id = resp.json()["id"]

    admin_headers = _login_admin(test_client)
    resp = test_client.post(
        f"/api/information/admin/posts/{post_id}/review",
        headers=admin_headers,
        json={"approved": False},
    )
    assert resp.status_code == 400

    resp = test_client.post(
        f"/api/information/admin/posts/{post_id}/review",
        headers=admin_headers,
        json={"approved": False, "reject_reason": "信息与类目不符"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["reject_reason"] == "信息与类目不符"
