# -*- coding: utf-8 -*-
"""收藏/关注与浏览足迹端到端测试。"""

from __future__ import annotations

from datetime import datetime, timezone

from src.server.auth import service as auth_service

from src.server.auth.tests._auth_router_helpers import _auth_headers
from src.server.mall.tests._compliance_helpers import (
    complete_shop_onboarding,
    shop_application_payload,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _register(
    test_client, *, username: str, email: str, password: str = "Password123"
):
    resp = test_client.post("/api/auth/send-verification-code", json={"email": email})
    assert resp.status_code == 200, resp.text
    code = auth_service.verification_codes[email]["code"]
    resp = test_client.post(
        "/api/auth/register-with-code",
        json={
            "username": username,
            "email": email,
            "password": password,
            "code": code,
        },
    )
    assert resp.status_code == 201, resp.text
    return username


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


def _seed_shop(test_client, *, seller_headers, admin_headers, name="收藏测试店"):
    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json=shop_application_payload(test_client, seller_headers, name=name),
        headers=seller_headers,
    )
    assert resp.status_code == 201, resp.text
    shop_id = resp.json()["id"]
    complete_shop_onboarding(test_client, seller_headers, admin_headers, shop_id)
    return shop_id


def _create_goods(test_client, *, seller_headers, price_fen=9900, name="收藏测试商品"):
    resp = test_client.post(
        "/api/mall/seller/goods",
        json={
            "name": name,
            "main_image": "/mall/goods-1.svg",
            "images": ["/mall/goods-1.svg"],
            "detail": "收藏测试详情",
            "skus": [
                {"specs": {"颜色": "红色"}, "price_fen": price_fen, "stock": 20},
            ],
        },
        headers=seller_headers,
    )
    assert resp.status_code == 201, resp.text
    goods = resp.json()
    resp = test_client.post(
        f"/api/mall/seller/goods/{goods['id']}/status?on=true",
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    return goods


# ---------------------------------------------------------------------------
# 收藏：增删幂等、列表快照、状态查询
# ---------------------------------------------------------------------------


def test_favorite_add_remove_and_list(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="fv-seller", email="fv-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="fv-buyer", email="fv-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id = _seed_shop(test_client, seller_headers=seller_headers, admin_headers=admin_headers)
    goods = _create_goods(test_client, seller_headers=seller_headers, price_fen=8800)

    # 收藏商品
    resp = test_client.post(
        "/api/mall/favorites",
        json={"target_type": "goods", "target_id": goods["id"]},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    fav = resp.json()
    assert fav["target_name"] == goods["name"]
    assert fav["target_price_fen"] == 8800
    assert fav["shop_id"] == shop_id

    # 重复收藏幂等（不再新建）
    resp = test_client.post(
        "/api/mall/favorites",
        json={"target_type": "goods", "target_id": goods["id"]},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == fav["id"]

    # 收藏店铺
    resp = test_client.post(
        "/api/mall/favorites",
        json={"target_type": "shop", "target_id": shop_id},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["target_name"] == "收藏测试店"
    assert resp.json()["target_price_fen"] is None

    # 状态查询
    resp = test_client.get(
        f"/api/mall/favorites/status?target_type=goods&target_id={goods['id']}",
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["favorited"] is True
    resp = test_client.get(
        "/api/mall/favorites/status?target_type=goods&target_id=999999",
        headers=buyer_headers,
    )
    assert resp.json()["favorited"] is False

    # 列表按类型筛选
    resp = test_client.get("/api/mall/favorites?target_type=goods", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["target_id"] == goods["id"]
    resp = test_client.get("/api/mall/favorites?target_type=shop", headers=buyer_headers)
    assert resp.json()["total"] == 1

    # 取消收藏（幂等）
    resp = test_client.delete(
        f"/api/mall/favorites?target_type=goods&target_id={goods['id']}",
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = test_client.delete(
        f"/api/mall/favorites?target_type=goods&target_id={goods['id']}",
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = test_client.get("/api/mall/favorites?target_type=goods", headers=buyer_headers)
    assert resp.json()["total"] == 0


def test_favorite_requires_login(test_client, test_db_session, init_test_database):
    # 未登录 401
    resp = test_client.get("/api/mall/favorites")
    assert resp.status_code == 401
    resp = test_client.post(
        "/api/mall/favorites", json={"target_type": "goods", "target_id": 1}
    )
    assert resp.status_code == 401


def test_favorite_invalid_target(test_client, test_db_session, init_test_database):
    buyer_headers = _login(test_client, username=_register(test_client, username="fi-buyer", email="fi-buyer@test.com"))

    # 收藏不存在的商品 404
    resp = test_client.post(
        "/api/mall/favorites",
        json={"target_type": "goods", "target_id": 999999},
        headers=buyer_headers,
    )
    assert resp.status_code == 404, resp.text

    # 收藏未审核店铺 404
    resp = test_client.post(
        "/api/mall/favorites",
        json={"target_type": "shop", "target_id": 999999},
        headers=buyer_headers,
    )
    assert resp.status_code == 404, resp.text

    # 非法类型 422
    resp = test_client.post(
        "/api/mall/favorites",
        json={"target_type": "bogus", "target_id": 1},
        headers=buyer_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 浏览足迹：upsert、倒序列表
# ---------------------------------------------------------------------------


def test_footprint_upsert_and_list(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="fp-seller", email="fp-seller@test.com"))
    buyer1_headers = _login(test_client, username=_register(test_client, username="fp-buyer1", email="fp-buyer1@test.com"))
    buyer2_headers = _login(test_client, username=_register(test_client, username="fp-buyer2", email="fp-buyer2@test.com"))
    admin_headers = _login_admin(test_client)

    _seed_shop(test_client, seller_headers=seller_headers, admin_headers=admin_headers)
    goods_a = _create_goods(test_client, seller_headers=seller_headers, price_fen=1000, name="足迹商品甲")
    goods_b = _create_goods(test_client, seller_headers=seller_headers, price_fen=2000, name="足迹商品乙")

    # 浏览 A，再浏览 B，再浏览 A（upsert：A 只保留一条且时间更新）
    for goods_id in (goods_a["id"], goods_b["id"], goods_a["id"]):
        resp = test_client.post(
            f"/api/mall/footprints?goods_id={goods_id}", headers=buyer1_headers
        )
        assert resp.status_code == 200, resp.text

    resp = test_client.get("/api/mall/footprints", headers=buyer1_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    # 倒序：最近浏览的 A 在最前
    assert body["items"][0]["goods_id"] == goods_a["id"]
    assert body["items"][1]["goods_id"] == goods_b["id"]
    assert body["items"][0]["goods_name"] == "足迹商品甲"
    assert body["items"][0]["price_fen"] == 1000
    assert body["items"][0]["shop_name"] == "收藏测试店"

    # 库内仅两条记录（upsert 生效）
    test_db_session.expire_all()
    from src.server.mall.models import Footprint

    count = test_db_session.query(Footprint).count()
    assert count == 2

    # 不同用户足迹相互独立
    resp = test_client.post(
        f"/api/mall/footprints?goods_id={goods_b['id']}", headers=buyer2_headers
    )
    assert resp.status_code == 200, resp.text
    resp = test_client.get("/api/mall/footprints", headers=buyer2_headers)
    assert resp.json()["total"] == 1

    # 足迹记录下架商品静默忽略（不报错）
    resp = test_client.post("/api/mall/footprints?goods_id=999999", headers=buyer1_headers)
    assert resp.status_code == 200, resp.text
