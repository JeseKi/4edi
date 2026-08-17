# -*- coding: utf-8 -*-
"""商品评价/晒单端到端测试：评价、评分汇总、追评、卖家回复、待评价列表、权限。"""

from __future__ import annotations

from src.server.auth import service as auth_service
from src.server.mall.schemas import EvaluationOut, OrderOut

from src.server.auth.tests._auth_router_helpers import _auth_headers


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


def _seed_shop(test_client, *, seller_headers, admin_headers):
    """申请店铺并通过审核。返回 shop_id。"""
    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json={"name": "评价测试店", "description": "自动化测试店铺", "real_name": "测试商家", "identity_number": "110101199001011234", "business_license_asset_id": "license", "identity_front_asset_id": "id-front", "identity_back_asset_id": "id-back"},
        headers=seller_headers,
    )
    assert resp.status_code == 201, resp.text
    shop_id = resp.json()["id"]

    resp = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/review",
        json={"approved": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return shop_id


def _create_goods(test_client, *, seller_headers, name="评价测试商品"):
    """创建商品并上架。返回 (goods_id, sku_id)。"""
    resp = test_client.post(
        "/api/mall/seller/goods",
        json={
            "name": name,
            "main_image": "/mall/goods-1.svg",
            "images": ["/mall/goods-1.svg"],
            "detail": "评价测试详情",
            "skus": [
                {"specs": {"颜色": "红色"}, "price_fen": 9900, "stock": 10},
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

    resp = test_client.get(
        f"/api/mall/seller/goods/{goods['id']}", headers=seller_headers
    )
    sku_id = resp.json()["skus"][0]["id"]
    return goods["id"], sku_id


def _seed_shop_and_goods(test_client, *, seller_headers, admin_headers, name="评价测试商品"):
    """申请店铺 → 审核 → 创建商品并上架。返回 (shop_id, goods_id, sku_id)。"""
    shop_id = _seed_shop(test_client, seller_headers=seller_headers, admin_headers=admin_headers)
    goods_id, sku_id = _create_goods(test_client, seller_headers=seller_headers, name=name)
    return shop_id, goods_id, sku_id


def _add_address(test_client, buyer_headers):
    resp = test_client.post(
        "/api/mall/addresses",
        json={
            "receiver": "张三",
            "phone": "13800138000",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园 1 号",
            "is_default": True,
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_paid_order(test_client, *, buyer_headers, sku_id, quantity=1):
    """下单并 mock 支付成功。返回 order_no。"""
    address_id = _add_address(test_client, buyer_headers)
    resp = test_client.post(
        "/api/mall/orders",
        json={
            "address_id": address_id,
            "items": [{"sku_id": sku_id, "quantity": quantity}],
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    order = OrderOut.model_validate(resp.json())
    resp = test_client.post(
        f"/api/mall/orders/{order.order_no}/payment",
        json={"pay_type": "native"},
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    out_trade_no = resp.json()["out_trade_no"]
    resp = test_client.post(
        f"/api/mall/payments/{out_trade_no}/mock-pay",
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"
    return order.order_no


def _ship_and_confirm(test_client, *, seller_headers, buyer_headers, order_no):
    """发货 → 确认收货，订单进入已完成。"""
    resp = test_client.post(
        f"/api/mall/seller/orders/{order_no}/ship",
        json={"shipping_company": "顺丰速运", "tracking_no": "SF1234567890"},
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/confirm", headers=buyer_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"


def _first_order_item_id(test_client, buyer_headers, order_no):
    resp = test_client.get(f"/api/mall/orders/{order_no}", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["items"][0]["id"]


def _evaluate(test_client, *, buyer_headers, order_no, item_id, rating=5, content="非常满意"):
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/evaluations",
        json={"order_item_id": item_id, "rating": rating, "content": content},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    return EvaluationOut.model_validate(resp.json())


# ---------------------------------------------------------------------------
# 状态校验与重复评价
# ---------------------------------------------------------------------------


def test_evaluation_requires_completed_order_and_dedup(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="ev-seller", email="ev-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="ev-buyer", email="ev-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    # 未确认收货不可评价（已支付状态）
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/evaluations",
        json={"order_item_id": 999, "rating": 5, "content": "想提前评价"},
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    _ship_and_confirm(
        test_client, seller_headers=seller_headers, buyer_headers=buyer_headers, order_no=order_no
    )
    item_id = _first_order_item_id(test_client, buyer_headers, order_no)

    # 评价成功
    evaluation = _evaluate(
        test_client, buyer_headers=buyer_headers, order_no=order_no, item_id=item_id
    )
    assert evaluation.rating == 5
    assert evaluation.buyer_username == "ev-buyer"
    assert evaluation.goods_name == "评价测试商品"
    assert evaluation.goods_id == goods_id

    # 重复评价 400
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/evaluations",
        json={"order_item_id": item_id, "rating": 4, "content": "再来一次"},
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    # 非本人订单 404
    other_buyer_headers = _login(
        test_client,
        username=_register(test_client, username="ev-other", email="ev-other@test.com"),
    )
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/evaluations",
        json={"order_item_id": item_id, "rating": 5, "content": "冒名评价"},
        headers=other_buyer_headers,
    )
    assert resp.status_code == 404, resp.text

    # 评分越界 422
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/evaluations",
        json={"order_item_id": item_id, "rating": 6, "content": "越界"},
        headers=buyer_headers,
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 评价列表与评分汇总
# ---------------------------------------------------------------------------


def test_evaluation_list_and_summary(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="ls-seller", email="ls-seller@test.com"))
    buyer1_headers = _login(test_client, username=_register(test_client, username="ls-buyer1", email="ls-buyer1@test.com"))
    buyer2_headers = _login(test_client, username=_register(test_client, username="ls-buyer2", email="ls-buyer2@test.com"))
    admin_headers = _login_admin(test_client)

    _, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    order_no1 = _create_paid_order(test_client, buyer_headers=buyer1_headers, sku_id=sku_id)
    _ship_and_confirm(test_client, seller_headers=seller_headers, buyer_headers=buyer1_headers, order_no=order_no1)
    item_id1 = _first_order_item_id(test_client, buyer1_headers, order_no1)
    _evaluate(test_client, buyer_headers=buyer1_headers, order_no=order_no1, item_id=item_id1, rating=5)

    order_no2 = _create_paid_order(test_client, buyer_headers=buyer2_headers, sku_id=sku_id)
    _ship_and_confirm(test_client, seller_headers=seller_headers, buyer_headers=buyer2_headers, order_no=order_no2)
    item_id2 = _first_order_item_id(test_client, buyer2_headers, order_no2)
    _evaluate(test_client, buyer_headers=buyer2_headers, order_no=order_no2, item_id=item_id2, rating=3, content="一般般")

    # 公开接口：列表 + 评分汇总（avg 4.0，好评率 50%）
    resp = test_client.get(f"/api/mall/goods/{goods_id}/evaluations")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 2
    assert data["summary"]["avg_rating"] == 4.0
    assert data["summary"]["rating_count"] == 2
    assert data["summary"]["good_rate"] == 50.0
    assert data["items"][0]["buyer_username"] == "ls-buyer2"  # 时间倒序

    # 我的评价列表
    resp = test_client.get("/api/mall/evaluations/mine", headers=buyer1_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["order_no"] == order_no1


# ---------------------------------------------------------------------------
# 追评
# ---------------------------------------------------------------------------


def test_append_evaluation(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="ap-seller", email="ap-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="ap-buyer", email="ap-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)
    _ship_and_confirm(test_client, seller_headers=seller_headers, buyer_headers=buyer_headers, order_no=order_no)
    item_id = _first_order_item_id(test_client, buyer_headers, order_no)
    evaluation = _evaluate(test_client, buyer_headers=buyer_headers, order_no=order_no, item_id=item_id)

    # 追评一次
    resp = test_client.post(
        f"/api/mall/evaluations/{evaluation.id}/append",
        json={"content": "用了几天，质量不错", "images": ["/img/b.png"]},
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["append_content"] == "用了几天，质量不错"
    assert resp.json()["append_images"] == ["/img/b.png"]
    assert resp.json()["appended_at"] is not None

    # 重复追评 400
    resp = test_client.post(
        f"/api/mall/evaluations/{evaluation.id}/append",
        json={"content": "再次追评"},
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    # 他人追评 404
    other_buyer_headers = _login(
        test_client,
        username=_register(test_client, username="ap-other", email="ap-other@test.com"),
    )
    resp = test_client.post(
        f"/api/mall/evaluations/{evaluation.id}/append",
        json={"content": "冒名追评"},
        headers=other_buyer_headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# 卖家回复
# ---------------------------------------------------------------------------


def test_seller_reply_evaluation(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="rp-seller", email="rp-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="rp-buyer", email="rp-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)
    _ship_and_confirm(test_client, seller_headers=seller_headers, buyer_headers=buyer_headers, order_no=order_no)
    item_id = _first_order_item_id(test_client, buyer_headers, order_no)
    evaluation = _evaluate(test_client, buyer_headers=buyer_headers, order_no=order_no, item_id=item_id)

    # 卖家回复
    resp = test_client.post(
        f"/api/mall/seller/evaluations/{evaluation.id}/reply",
        json={"content": "感谢您的支持！"},
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["seller_reply"] == "感谢您的支持！"
    assert resp.json()["seller_replied_at"] is not None

    # 可覆盖回复
    resp = test_client.post(
        f"/api/mall/seller/evaluations/{evaluation.id}/reply",
        json={"content": "欢迎再次光临"},
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["seller_reply"] == "欢迎再次光临"

    # 店铺评价列表
    resp = test_client.get("/api/mall/seller/evaluations", headers=seller_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    # 非本店卖家回复 404
    other_seller_headers = _login(
        test_client,
        username=_register(test_client, username="rp-other", email="rp-other@test.com"),
    )
    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json={"name": "另一家店", "real_name": "测试商家", "identity_number": "110101199001011234", "business_license_asset_id": "license", "identity_front_asset_id": "id-front", "identity_back_asset_id": "id-back"},
        headers=other_seller_headers,
    )
    assert resp.status_code == 201, resp.text
    other_shop_id = resp.json()["id"]
    resp = test_client.post(
        f"/api/mall/admin/shops/{other_shop_id}/review",
        json={"approved": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    resp = test_client.post(
        f"/api/mall/seller/evaluations/{evaluation.id}/reply",
        json={"content": "抢回复"},
        headers=other_seller_headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# 待评价列表
# ---------------------------------------------------------------------------


def test_pending_evaluations(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="pe-seller", email="pe-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="pe-buyer", email="pe-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id = _seed_shop(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    goods_id1, sku_id1 = _create_goods(
        test_client, seller_headers=seller_headers, name="评价商品甲"
    )
    goods_id2, sku_id2 = _create_goods(
        test_client, seller_headers=seller_headers, name="评价商品乙"
    )

    order_no1 = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id1)
    _ship_and_confirm(test_client, seller_headers=seller_headers, buyer_headers=buyer_headers, order_no=order_no1)
    order_no2 = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id2)
    _ship_and_confirm(test_client, seller_headers=seller_headers, buyer_headers=buyer_headers, order_no=order_no2)

    # 两个待评价
    resp = test_client.get("/api/mall/evaluations/pending", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2

    # 评价商品甲后，待评价只剩商品乙
    item_id1 = _first_order_item_id(test_client, buyer_headers, order_no1)
    _evaluate(test_client, buyer_headers=buyer_headers, order_no=order_no1, item_id=item_id1)

    resp = test_client.get("/api/mall/evaluations/pending", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    pending = resp.json()
    assert len(pending) == 1
    assert pending[0]["goods_id"] == goods_id2
    assert pending[0]["goods_name"] == "评价商品乙"
    assert pending[0]["order_no"] == order_no2
    assert pending[0]["shop_id"] == shop_id
    assert pending[0]["shop_name"] == "评价测试店"

    # 未登录 401
    resp = test_client.get("/api/mall/evaluations/pending")
    assert resp.status_code == 401, resp.text
