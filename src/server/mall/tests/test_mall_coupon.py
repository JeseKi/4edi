# -*- coding: utf-8 -*-
"""优惠券端到端测试：领券限制、满减/折扣计算、下单用券、券管理、过期清理。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.server.auth import service as auth_service
from src.server.mall import service as mall_service
from src.server.mall.dao import UserCouponDAO
from src.server.mall.models import UserCouponStatus
from src.server.mall.schemas import OrderOut

from src.server.auth.tests._auth_router_helpers import _auth_headers


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(offset_days: int) -> str:
    return (_utcnow() + timedelta(days=offset_days)).isoformat()


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


def _seed_shop(test_client, *, seller_headers, admin_headers, name="优惠券测试店"):
    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json={"name": name, "description": "自动化测试店铺", "real_name": "测试商家", "identity_number": "110101199001011234", "business_license_asset_id": "license", "identity_front_asset_id": "id-front", "identity_back_asset_id": "id-back"},
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


def _create_goods(test_client, *, seller_headers, price_fen=9900, name="优惠券测试商品"):
    resp = test_client.post(
        "/api/mall/seller/goods",
        json={
            "name": name,
            "main_image": "/mall/goods-1.svg",
            "images": ["/mall/goods-1.svg"],
            "detail": "优惠券测试详情",
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
    resp = test_client.get(
        f"/api/mall/seller/goods/{goods['id']}", headers=seller_headers
    )
    return resp.json()["skus"][0]["id"]


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


def _create_order(
    test_client, *, buyer_headers, sku_id, quantity=2, coupon_id=None, expect=201
):
    address_id = _add_address(test_client, buyer_headers)
    payload = {
        "address_id": address_id,
        "items": [{"sku_id": sku_id, "quantity": quantity}],
    }
    if coupon_id is not None:
        payload["coupon_id"] = coupon_id
    resp = test_client.post("/api/mall/orders", json=payload, headers=buyer_headers)
    assert resp.status_code == expect, resp.text
    return resp.json()


def _admin_create_coupon(test_client, admin_headers, payload):
    resp = test_client.post("/api/mall/admin/coupons", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _receive_coupon(test_client, buyer_headers, coupon_id, expect=201):
    resp = test_client.post(
        f"/api/mall/coupons/{coupon_id}/receive", headers=buyer_headers
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 领券限制：超发、限领、过期券
# ---------------------------------------------------------------------------


def test_coupon_receive_limits(test_client, test_db_session, init_test_database):
    buyer1_headers = _login(test_client, username=_register(test_client, username="cl-buyer1", email="cl-buyer1@test.com"))
    buyer2_headers = _login(test_client, username=_register(test_client, username="cl-buyer2", email="cl-buyer2@test.com"))
    admin_headers = _login_admin(test_client)

    # 限量 1 张
    limited = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "限量满减券",
            "type": "fixed",
            "value_fen": 1000,
            "min_amount_fen": 5000,
            "scope": "platform",
            "total_count": 1,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    # 每人限领 1 张（不限量）
    per_user = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "限领折扣券",
            "type": "discount",
            "discount": 90,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    # 已过期券
    expired = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "过期券",
            "type": "fixed",
            "value_fen": 500,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-8),
            "valid_until": _iso(-1),
        },
    )

    # buyer1 领限量券成功，buyer2 领失败（已领完）
    _receive_coupon(test_client, buyer1_headers, limited["id"])
    _receive_coupon(test_client, buyer2_headers, limited["id"], expect=400)

    # 重复领取限领券失败
    _receive_coupon(test_client, buyer1_headers, per_user["id"])
    _receive_coupon(test_client, buyer1_headers, per_user["id"], expect=400)
    # 其他用户可领
    _receive_coupon(test_client, buyer2_headers, per_user["id"])

    # 过期券不可领
    _receive_coupon(test_client, buyer1_headers, expired["id"], expect=400)

    # 领券中心只展示进行中的有效券（限量券已领完 → 不再展示）
    resp = test_client.get("/api/mall/coupons", headers=buyer1_headers)
    assert resp.status_code == 200, resp.text
    names = {item["name"] for item in resp.json()["items"]}
    assert "限领折扣券" in names
    assert "限量满减券" not in names
    assert "过期券" not in names

    # 我的优惠券列表
    resp = test_client.get("/api/mall/coupons/mine?status=unused", headers=buyer1_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# 满减/折扣计算、门槛、店铺范围
# ---------------------------------------------------------------------------


def test_coupon_discount_calculation(test_client, test_db_session, init_test_database):
    seller1_headers = _login(test_client, username=_register(test_client, username="cd-seller1", email="cd-seller1@test.com"))
    seller2_headers = _login(test_client, username=_register(test_client, username="cd-seller2", email="cd-seller2@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="cd-buyer", email="cd-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    shop1_id = _seed_shop(test_client, seller_headers=seller1_headers, admin_headers=admin_headers, name="店铺甲")
    _seed_shop(test_client, seller_headers=seller2_headers, admin_headers=admin_headers, name="店铺乙")
    sku1 = _create_goods(test_client, seller_headers=seller1_headers, price_fen=9900, name="商品甲")
    sku2 = _create_goods(test_client, seller_headers=seller2_headers, price_fen=9900, name="商品乙")

    # 平台满减券：满 10000 减 2000
    fixed = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "满减券",
            "type": "fixed",
            "value_fen": 2000,
            "min_amount_fen": 10000,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    # 平台折扣券：9 折
    discount_c = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "九折券",
            "type": "discount",
            "discount": 90,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    # 店铺甲专用券
    shop_coupon = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "店铺甲专享券",
            "type": "fixed",
            "value_fen": 500,
            "min_amount_fen": 0,
            "scope": "shop",
            "shop_id": shop1_id,
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    assert shop_coupon["scope"] == "shop"
    assert shop_coupon["shop_id"] == shop1_id
    assert shop_coupon["shop_name"] == "店铺甲"

    _receive_coupon(test_client, buyer_headers, fixed["id"])
    _receive_coupon(test_client, buyer_headers, discount_c["id"])
    _receive_coupon(test_client, buyer_headers, shop_coupon["id"])

    # 1 件 9900 < 门槛 10000 → 不可用
    resp = test_client.post(
        "/api/mall/orders/preview",
        json={
            "items": [{"sku_id": sku1, "quantity": 1}],
            "coupon_id": fixed["id"],
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    # 2 件 19800 → 满减 2000，运费 0（默认）
    resp = test_client.post(
        "/api/mall/orders/preview",
        json={
            "items": [{"sku_id": sku1, "quantity": 2}],
            "coupon_id": fixed["id"],
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["goods_amount_fen"] == 19800
    assert resp.json()["coupon_discount_fen"] == 2000
    assert resp.json()["pay_amount_fen"] == 17800

    # 9 折券：19800 → 折扣 1980
    resp = test_client.post(
        "/api/mall/orders/preview",
        json={
            "items": [{"sku_id": sku1, "quantity": 2}],
            "coupon_id": discount_c["id"],
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["coupon_discount_fen"] == 1980
    assert resp.json()["pay_amount_fen"] == 17820

    # 店铺券用于店铺乙商品 → 400
    resp = test_client.post(
        "/api/mall/orders/preview",
        json={
            "items": [{"sku_id": sku2, "quantity": 2}],
            "coupon_id": shop_coupon["id"],
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    # 店铺券用于店铺甲商品 → 可用
    resp = test_client.post(
        "/api/mall/orders/preview",
        json={
            "items": [{"sku_id": sku1, "quantity": 2}],
            "coupon_id": shop_coupon["id"],
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["coupon_discount_fen"] == 500


# ---------------------------------------------------------------------------
# 下单用券：金额扣减、券置已使用、订单详情
# ---------------------------------------------------------------------------


def test_order_with_coupon(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="oc-seller", email="oc-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="oc-buyer", email="oc-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _seed_shop(test_client, seller_headers=seller_headers, admin_headers=admin_headers)
    sku_id = _create_goods(test_client, seller_headers=seller_headers)

    coupon = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "下单满减券",
            "type": "fixed",
            "value_fen": 2000,
            "min_amount_fen": 10000,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 2,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    user_coupon = _receive_coupon(test_client, buyer_headers, coupon["id"])
    assert user_coupon["status"] == "unused"
    assert user_coupon["name"] == "下单满减券"

    # 下单带券：19800 - 2000 = 17800
    order = _create_order(
        test_client, buyer_headers=buyer_headers, sku_id=sku_id, quantity=2, coupon_id=coupon["id"]
    )
    order_out = OrderOut.model_validate(order)
    assert order_out.pay_amount_fen == 17800
    assert order_out.coupon_id == coupon["id"]
    assert order_out.coupon_discount_fen == 2000

    # 券已使用且关联订单
    resp = test_client.get("/api/mall/coupons/mine?status=used", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1
    used = resp.json()["items"][0]
    assert used["order_no"] == order_out.order_no
    assert used["used_at"] is not None

    # 已使用券不可再次下单
    _create_order(
        test_client,
        buyer_headers=buyer_headers,
        sku_id=sku_id,
        quantity=2,
        coupon_id=coupon["id"],
        expect=400,
    )

    # 订单详情带优惠信息
    resp = test_client.get(f"/api/mall/orders/{order_out.order_no}", headers=buyer_headers)
    assert resp.json()["coupon_discount_fen"] == 2000


# ---------------------------------------------------------------------------
# 券管理：卖家 CRUD、上下架、跨店越权
# ---------------------------------------------------------------------------


def test_coupon_management(test_client, test_db_session, init_test_database):
    seller1_headers = _login(test_client, username=_register(test_client, username="cm-seller1", email="cm-seller1@test.com"))
    seller2_headers = _login(test_client, username=_register(test_client, username="cm-seller2", email="cm-seller2@test.com"))
    admin_headers = _login_admin(test_client)

    shop1_id = _seed_shop(test_client, seller_headers=seller1_headers, admin_headers=admin_headers, name="管理店甲")
    _seed_shop(test_client, seller_headers=seller2_headers, admin_headers=admin_headers, name="管理店乙")

    # 卖家创建店铺券
    resp = test_client.post(
        "/api/mall/seller/coupons",
        json={
            "name": "店铺满减券",
            "type": "fixed",
            "value_fen": 800,
            "min_amount_fen": 5000,
            "total_count": 100,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
        headers=seller1_headers,
    )
    assert resp.status_code == 201, resp.text
    coupon = resp.json()
    assert coupon["scope"] == "shop"
    assert coupon["shop_id"] == shop1_id

    # 卖家列表
    resp = test_client.get("/api/mall/seller/coupons", headers=seller1_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    # 更新
    resp = test_client.put(
        f"/api/mall/seller/coupons/{coupon['id']}",
        json={"name": "店铺满减券（改）"},
        headers=seller1_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "店铺满减券（改）"

    # 下架 → 领券中心不可见；上架恢复
    resp = test_client.post(
        f"/api/mall/seller/coupons/{coupon['id']}/status?on=false",
        headers=seller1_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "paused"
    resp = test_client.post(
        f"/api/mall/seller/coupons/{coupon['id']}/status?on=true",
        headers=seller1_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "active"

    # 跨店越权：seller2 无法更新/下架 seller1 的券
    resp = test_client.put(
        f"/api/mall/seller/coupons/{coupon['id']}",
        json={"name": "越权修改"},
        headers=seller2_headers,
    )
    assert resp.status_code == 404, resp.text

    # 管理员创建平台券 + 上下架
    platform = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "平台券",
            "type": "fixed",
            "value_fen": 300,
            "min_amount_fen": 1000,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    assert platform["scope"] == "platform"
    assert platform["shop_id"] is None

    resp = test_client.get("/api/mall/admin/coupons", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 2

    resp = test_client.post(
        f"/api/mall/admin/coupons/{platform['id']}/status?on=false",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "paused"

    # 店铺券创建必须指定 shop_id
    resp = test_client.post(
        "/api/mall/admin/coupons",
        json={
            "name": "缺店铺券",
            "type": "fixed",
            "value_fen": 100,
            "scope": "shop",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# 过期清理 worker
# ---------------------------------------------------------------------------


def test_coupon_expire_worker(test_client, test_db_session, init_test_database):
    buyer_headers = _login(test_client, username=_register(test_client, username="ew-buyer", email="ew-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    # 已过有效期的券模板（创建后仍为 ACTIVE）
    expired_template = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "已过期模板",
            "type": "fixed",
            "value_fen": 100,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-8),
            "valid_until": _iso(-1),
        },
    )
    assert expired_template["status"] == "active"

    # 有效券：领券后把用户券有效期改到过去
    active_template = _admin_create_coupon(
        test_client,
        admin_headers,
        {
            "name": "将过期用户券",
            "type": "fixed",
            "value_fen": 100,
            "scope": "platform",
            "total_count": 0,
            "per_user_limit": 1,
            "valid_from": _iso(-1),
            "valid_until": _iso(7),
        },
    )
    user_coupon = _receive_coupon(test_client, buyer_headers, active_template["id"])
    assert user_coupon["status"] == "unused"

    def _backdate(db):
        item = UserCouponDAO(db).get(user_coupon["id"])
        item.expired_at = _utcnow() - timedelta(hours=1)

    _backdate(test_db_session)
    test_db_session.commit()

    # worker 清理：模板与用户券均置过期
    result = mall_service.expire_coupons(test_db_session)
    assert result["templates"] == 1
    assert result["user_coupons"] == 1
    test_db_session.commit()

    assert UserCouponDAO(test_db_session).get(user_coupon["id"]).status == UserCouponStatus.EXPIRED

    # 幂等：重复清理不再变化
    result2 = mall_service.expire_coupons(test_db_session)
    assert result2["templates"] == 0
    assert result2["user_coupons"] == 0
    test_db_session.commit()

    # 查询我的优惠券：状态已同步为 expired
    resp = test_client.get("/api/mall/coupons/mine?status=expired", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1
