# -*- coding: utf-8 -*-
"""商城端到端路由测试：开店审核、商品、购物车、下单支付、发货收货、资金、提现、客服。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.server.auth import service as auth_service
from src.server.mall import service as mall_service
from src.server.mall.dao import OrderDAO, PaymentDAO, WalletDAO
from src.server.mall.models import (
    LedgerStatus,
    LedgerType,
    OrderStatus,
    PaymentStatus,
)
from src.server.mall.schemas import OrderPreviewOut, OrderOut

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


def _seed_shop_and_goods(test_client, *, seller_headers, admin_headers):
    """申请店铺 → 管理员审核 → 创建商品并上架。返回 (shop_id, goods_id, sku_id)。"""
    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json={"name": "测试旗舰店", "description": "自动化测试店铺", "real_name": "测试商家", "identity_number": "110101199001011234", "business_license_asset_id": "license", "identity_front_asset_id": "id-front", "identity_back_asset_id": "id-back"},
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
    assert resp.json()["status"] == "approved"

    resp = test_client.post(
        "/api/mall/seller/goods",
        json={
            "name": "测试商品",
            "main_image": "/mall/goods-1.svg",
            "images": ["/mall/goods-1.svg"],
            "detail": "测试商品详情",
            "original_price_fen": 12900,
            "skus": [
                {"specs": {"颜色": "红色"}, "price_fen": 9900, "stock": 10},
                {"specs": {"颜色": "蓝色"}, "price_fen": 10900, "stock": 5},
            ],
        },
        headers=seller_headers,
    )
    assert resp.status_code == 201, resp.text
    goods = resp.json()
    assert goods["price_fen"] == 9900
    assert goods["stock"] == 15

    resp = test_client.post(
        f"/api/mall/seller/goods/{goods['id']}/status?on=true",
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "on"

    sku_id = None
    resp = test_client.get(
        f"/api/mall/seller/goods/{goods['id']}", headers=seller_headers
    )
    assert resp.status_code == 200, resp.text
    sku_id = resp.json()["skus"][0]["id"]

    return shop_id, goods["id"], sku_id


def test_full_buyer_seller_flow(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="seller1", email="seller1@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="buyer1", email="buyer1@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    # 买家浏览公开商品
    resp = test_client.get("/api/mall/goods")
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    resp = test_client.get(f"/api/mall/goods/{goods_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["shop"]["name"] == "测试旗舰店"
    assert len(resp.json()["skus"]) == 2

    # 加入购物车
    resp = test_client.post(
        "/api/mall/cart/items",
        json={"goods_id": goods_id, "sku_id": sku_id, "quantity": 2},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["subtotal_fen"] == 19800

    resp = test_client.get("/api/mall/cart", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1

    # 新增收货地址
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
    address_id = resp.json()["id"]

    # 预览订单
    resp = test_client.post(
        "/api/mall/orders/preview",
        json={"address_id": address_id, "items": [{"sku_id": sku_id, "quantity": 2}]},
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    preview = OrderPreviewOut.model_validate(resp.json())
    assert preview.goods_amount_fen == 19800
    assert preview.pay_amount_fen == 19800

    # 从购物车下单
    cart_item_id = test_client.get("/api/mall/cart", headers=buyer_headers).json()[0]["id"]
    resp = test_client.post(
        "/api/mall/orders",
        json={
            "address_id": address_id,
            "items": [{"sku_id": sku_id, "quantity": 2}],
            "cart_item_ids": [cart_item_id],
            "remark": "请尽快发货",
        },
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    order = OrderOut.model_validate(resp.json())
    assert order.status == OrderStatus.PENDING_PAYMENT
    assert order.pay_amount_fen == 19800
    assert order.items[0].quantity == 2

    # 购物车已清空
    resp = test_client.get("/api/mall/cart", headers=buyer_headers)
    assert resp.json() == []

    # 发起支付（mock 通道）
    resp = test_client.post(
        f"/api/mall/orders/{order.order_no}/payment",
        json={"pay_type": "native"},
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    pay = resp.json()
    assert pay["mode"] == "mock"
    assert pay["code_url"].startswith("weixin://")

    # 模拟支付成功
    resp = test_client.post(
        f"/api/mall/payments/{pay['out_trade_no']}/mock-pay",
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    # 订单已支付，货款冻结
    resp = test_client.get(f"/api/mall/orders/{order.order_no}", headers=buyer_headers)
    assert resp.json()["status"] == "paid"

    def _check_wallet(db):
        wallet = WalletDAO(db).get(shop_id)
        assert wallet is not None
        assert wallet.frozen_fen == 19800
        assert wallet.available_fen == 0

    _check_wallet(test_db_session)

    # 商家看到已支付订单并发货
    resp = test_client.get("/api/mall/seller/orders?status=paid", headers=seller_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    resp = test_client.post(
        f"/api/mall/seller/orders/{order.order_no}/ship",
        json={"shipping_company": "顺丰速运", "tracking_no": "SF1234567890"},
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    shipped = OrderOut.model_validate(resp.json())
    assert shipped.status == OrderStatus.SHIPPED
    assert len(shipped.shipping_traces) == 3

    # 买家查看物流轨迹
    resp = test_client.get(
        f"/api/mall/orders/{order.order_no}/traces", headers=buyer_headers
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["traces"]) == 3

    # 买家确认收货
    resp = test_client.post(
        f"/api/mall/orders/{order.order_no}/confirm", headers=buyer_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "completed"

    # 确认收货后物流轨迹追加完成节点
    resp = test_client.get(
        f"/api/mall/orders/{order.order_no}/traces", headers=buyer_headers
    )
    assert len(resp.json()["traces"]) == 4

    # 资金解冻到可用余额
    def _check_wallet_after_confirm(db):
        wallet = WalletDAO(db).get(shop_id)
        assert wallet is not None
        assert wallet.frozen_fen == 0
        assert wallet.available_fen == 19800
        ledgers = [
            row
            for row in _all_ledgers(db, shop_id)
            if row.entry_type == LedgerType.SALE
        ]
        assert len(ledgers) == 2
        assert ledgers[0].status == LedgerStatus.FROZEN
        assert ledgers[1].status == LedgerStatus.AVAILABLE
        assert ledgers[1].amount_fen == 19800

    _check_wallet_after_confirm(test_db_session)

    # 商品销量与库存
    resp = test_client.get(f"/api/mall/goods/{goods_id}")
    assert resp.json()["sales"] == 2
    assert resp.json()["stock"] == 13


def _all_ledgers(db, shop_id):
    from src.server.mall.models import WalletLedger

    return db.query(WalletLedger).filter(WalletLedger.shop_id == shop_id).order_by(WalletLedger.id.asc()).all()


def test_stock_deduction_and_cancel_restore(test_client, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="seller2", email="seller2@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="buyer2", email="buyer2@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    resp = test_client.post(
        "/api/mall/addresses",
        json={
            "receiver": "李四",
            "phone": "13800138001",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园 2 号",
        },
        headers=buyer_headers,
    )
    address_id = resp.json()["id"]

    # 下单 8 件（SKU1 库存 10）
    resp = test_client.post(
        "/api/mall/orders",
        json={"address_id": address_id, "items": [{"sku_id": sku_id, "quantity": 8}]},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    order_no = resp.json()["order_no"]

    # 库存已锁定
    resp = test_client.get(f"/api/mall/goods/{goods_id}")
    assert resp.json()["stock"] == 7

    # 取消订单恢复库存
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/cancel", headers=buyer_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    resp = test_client.get(f"/api/mall/goods/{goods_id}")
    assert resp.json()["stock"] == 15

    # 重复取消应失败
    resp = test_client.post(
        f"/api/mall/orders/{order_no}/cancel", headers=buyer_headers
    )
    assert resp.status_code == 400, resp.text


def test_insufficient_stock_rejected(test_client, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="seller3", email="seller3@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="buyer3", email="buyer3@test.com"))
    admin_headers = _login_admin(test_client)

    _, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    resp = test_client.post(
        "/api/mall/cart/items",
        json={"goods_id": goods_id, "sku_id": sku_id, "quantity": 99},
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "库存不足" in resp.json()["detail"]


def test_payment_timeout_task_cancels_order(test_db_session, test_client, init_test_database):
    """支付超时任务：订单超时后被自动取消并恢复库存。"""
    seller_headers = _login(test_client, username=_register(test_client, username="seller4", email="seller4@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="buyer4", email="buyer4@test.com"))
    admin_headers = _login_admin(test_client)

    _, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    resp = test_client.post(
        "/api/mall/addresses",
        json={
            "receiver": "王五",
            "phone": "13800138002",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园 3 号",
        },
        headers=buyer_headers,
    )
    address_id = resp.json()["id"]

    resp = test_client.post(
        "/api/mall/orders",
        json={"address_id": address_id, "items": [{"sku_id": sku_id, "quantity": 1}]},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    order_no = resp.json()["order_no"]

    # 把订单创建时间改到超时之前
    def _age_order(db):
        order = OrderDAO(db).get_by_no(order_no)
        assert order is not None
        order.created_at = datetime.now(timezone.utc) - timedelta(hours=2)

    _age_order(test_db_session)
    test_db_session.commit()

    mall_service.cancel_expired_order(test_db_session, order_no)

    def _check(db):
        order = OrderDAO(db).get_by_no(order_no)
        assert order.status == OrderStatus.CANCELLED
        assert order.cancel_reason == "支付超时，系统自动取消"
        from src.server.mall.dao import GoodsDAO, GoodsSkuDAO

        assert GoodsSkuDAO(db).get(sku_id).stock == 10
        assert GoodsDAO(db).get(goods_id).stock == 15

    _check(test_db_session)


def test_withdraw_flow(test_client, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="seller5", email="seller5@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="buyer5", email="buyer5@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    # 先完成一单，产生可提现余额
    resp = test_client.post(
        "/api/mall/addresses",
        json={
            "receiver": "赵六",
            "phone": "13800138003",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园 4 号",
        },
        headers=buyer_headers,
    )
    address_id = resp.json()["id"]
    resp = test_client.post(
        "/api/mall/orders",
        json={"address_id": address_id, "items": [{"sku_id": sku_id, "quantity": 1}]},
        headers=buyer_headers,
    )
    order_no = resp.json()["order_no"]
    pay = test_client.post(
        f"/api/mall/orders/{order_no}/payment", json={"pay_type": "native"}, headers=buyer_headers
    ).json()
    test_client.post(f"/api/mall/payments/{pay['out_trade_no']}/mock-pay", headers=buyer_headers)
    test_client.post(f"/api/mall/seller/orders/{order_no}/ship",
                     json={"shipping_company": "中通", "tracking_no": "ZT1"}, headers=seller_headers)
    test_client.post(f"/api/mall/orders/{order_no}/confirm", headers=buyer_headers)

    # 钱包含保证金与货款
    resp = test_client.get("/api/mall/seller/wallet", headers=seller_headers)
    wallet = resp.json()
    assert wallet["deposit_fen"] == 1000
    assert wallet["available_fen"] == 9900
    assert wallet["total_fen"] == 10900

    # 提现超出可用余额应失败
    resp = test_client.post(
        "/api/mall/seller/withdrawals",
        json={"amount_fen": 100000, "account_info": {"bank": "招商银行", "account": "6222****1234"}},
        headers=seller_headers,
    )
    assert resp.status_code == 400, resp.text

    # 正常提现 5000 分
    resp = test_client.post(
        "/api/mall/seller/withdrawals",
        json={"amount_fen": 5000, "account_info": {"bank": "招商银行", "account": "6222****1234"}},
        headers=seller_headers,
    )
    assert resp.status_code == 201, resp.text
    withdraw = resp.json()
    assert withdraw["status"] == "pending"

    resp = test_client.get("/api/mall/seller/wallet", headers=seller_headers)
    assert resp.json()["available_fen"] == 4900

    # 管理员驳回：退回可用余额
    resp = test_client.get("/api/mall/admin/withdrawals", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    resp = test_client.post(
        f"/api/mall/admin/withdrawals/{withdraw['id']}/handle",
        json={"approved": False, "reject_reason": "账户信息不符"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"

    resp = test_client.get("/api/mall/seller/wallet", headers=seller_headers)
    assert resp.json()["available_fen"] == 9900

    # 再次提现并审核通过
    resp = test_client.post(
        "/api/mall/seller/withdrawals",
        json={"amount_fen": 3000, "account_info": {"bank": "招商银行", "account": "6222****1234"}},
        headers=seller_headers,
    )
    withdraw2 = resp.json()
    resp = test_client.post(
        f"/api/mall/admin/withdrawals/{withdraw2['id']}/handle",
        json={"approved": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "paid"


def test_chat_messages(test_client, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="seller6", email="seller6@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="buyer6", email="buyer6@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    # 买家咨询
    resp = test_client.post(
        "/api/mall/chat/messages",
        json={"shop_id": shop_id, "content": "请问包邮吗？"},
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text

    # 商家回复（读取会标记买家消息已读）
    resp = test_client.get(
        f"/api/mall/seller/chat/messages?shop_id={shop_id}", headers=seller_headers
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 1

    resp = test_client.post(
        "/api/mall/seller/chat/messages",
        json={"shop_id": shop_id, "content": "全场包邮哦"},
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text

    # 买家会话列表与未读数
    resp = test_client.get("/api/mall/chat/conversations", headers=buyer_headers)
    conversations = resp.json()
    assert len(conversations) == 1
    assert conversations[0]["shop_name"] == "测试旗舰店"
    assert conversations[0]["unread_count"] == 1
    assert conversations[0]["last_message"] == "全场包邮哦"

    # 买家读取后未读清零
    resp = test_client.get(
        f"/api/mall/chat/messages?shop_id={shop_id}", headers=buyer_headers
    )
    assert len(resp.json()) == 2
    resp = test_client.get("/api/mall/chat/conversations", headers=buyer_headers)
    assert resp.json()[0]["unread_count"] == 0

    # 商家会话列表
    resp = test_client.get("/api/mall/seller/chat/conversations", headers=seller_headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["unread_count"] == 0


def test_admin_can_operate_any_shop_via_shop_id(test_client, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="seller7", email="seller7@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    # 管理员带 shop_id 创建商品
    resp = test_client.post(
        f"/api/mall/seller/goods?shop_id={shop_id}",
        json={
            "name": "管理员代发商品",
            "main_image": "/mall/goods-2.svg",
            "images": [],
            "skus": [{"specs": {}, "price_fen": 19900, "stock": 3}],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["shop_id"] == shop_id

    # 普通用户带 shop_id 应被拒绝
    resp = test_client.post(
        f"/api/mall/seller/goods?shop_id={shop_id}",
        json={
            "name": "越权商品",
            "main_image": "/mall/goods-3.svg",
            "images": [],
            "skus": [{"specs": {}, "price_fen": 100, "stock": 1}],
        },
        headers=seller_headers,
    )
    assert resp.status_code == 403, resp.text

    # 管理员查看该店铺资金
    resp = test_client.get(f"/api/mall/seller/wallet?shop_id={shop_id}", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["deposit_fen"] == 1000


def test_shop_review_and_close(test_client, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="seller8", email="seller8@test.com"))
    admin_headers = _login_admin(test_client)

    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json={"name": "缺材料店铺"},
        headers=seller_headers,
    )
    assert resp.status_code == 422, resp.text

    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json={"name": "待审核店铺", "real_name": "测试商家", "identity_number": "110101199001011234", "business_license_asset_id": "license", "identity_front_asset_id": "id-front", "identity_back_asset_id": "id-back"},
        headers=seller_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["real_name"] == "测试商家"
    assert resp.json()["business_license_asset_id"] == "license"
    shop_id = resp.json()["id"]

    # 审核通过前不能创建商品
    resp = test_client.post(
        "/api/mall/seller/goods",
        json={
            "name": "审核前商品",
            "main_image": "/mall/goods-1.svg",
            "images": [],
            "skus": [{"specs": {}, "price_fen": 100, "stock": 1}],
        },
        headers=seller_headers,
    )
    assert resp.status_code == 400, resp.text

    # 管理员拒绝
    resp = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/review",
        json={"approved": False, "reject_reason": "资料不全"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"

    # 重新申请应失败（已申请过）
    resp = test_client.post(
        "/api/mall/seller/shop/apply",
        json={"name": "再次申请", "real_name": "测试商家", "identity_number": "110101199001011234", "business_license_asset_id": "license", "identity_front_asset_id": "id-front", "identity_back_asset_id": "id-back"},
        headers=seller_headers,
    )
    assert resp.status_code == 400, resp.text

    # 审核通过后关闭店铺
    resp = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/review",
        json={"approved": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    resp = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/close", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"

    resp = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/reopen", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"


def test_payment_is_idempotent(test_client, test_db_session, init_test_database):
    """同一笔支付通知重复入账不会重复冻结资金。"""
    seller_headers = _login(test_client, username=_register(test_client, username="seller9", email="seller9@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="buyer9", email="buyer9@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )

    resp = test_client.post(
        "/api/mall/addresses",
        json={
            "receiver": "钱七",
            "phone": "13800138004",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园 5 号",
        },
        headers=buyer_headers,
    )
    address_id = resp.json()["id"]
    resp = test_client.post(
        "/api/mall/orders",
        json={"address_id": address_id, "items": [{"sku_id": sku_id, "quantity": 1}]},
        headers=buyer_headers,
    )
    order_no = resp.json()["order_no"]
    pay = test_client.post(
        f"/api/mall/orders/{order_no}/payment", json={"pay_type": "native"}, headers=buyer_headers
    ).json()
    out_trade_no = pay["out_trade_no"]

    for _ in range(3):
        resp = test_client.post(
            f"/api/mall/payments/{out_trade_no}/mock-pay", headers=buyer_headers
        )
        assert resp.status_code == 200, resp.text

    def _check(db):
        payment = PaymentDAO(db).get_by_out_trade_no(out_trade_no)
        assert payment.status == PaymentStatus.SUCCESS
        wallet = WalletDAO(db).get(shop_id)
        assert wallet.frozen_fen == 9900
        assert wallet.available_fen == 0
        order = OrderDAO(db).get_by_no(order_no)
        assert order.status == OrderStatus.PAID

    _check(test_db_session)


def test_payment_reuses_active_trade_and_supports_refresh(
    test_client, init_test_database
):
    seller_headers = _login(
        test_client, username=_register(test_client, username="seller10", email="seller10@test.com")
    )
    buyer_headers = _login(
        test_client, username=_register(test_client, username="buyer10", email="buyer10@test.com")
    )
    admin_headers = _login_admin(test_client)
    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    address = test_client.post(
        "/api/mall/addresses",
        json={
            "receiver": "支付复用用户",
            "phone": "13800138005",
            "province": "广东省",
            "city": "深圳市",
            "district": "南山区",
            "detail": "科技园 6 号",
        },
        headers=buyer_headers,
    ).json()
    order = test_client.post(
        "/api/mall/orders",
        json={"address_id": address["id"], "items": [{"sku_id": sku_id, "quantity": 1}]},
        headers=buyer_headers,
    ).json()

    first = test_client.post(
        f"/api/mall/orders/{order['order_no']}/payment",
        json={"pay_type": "native"},
        headers=buyer_headers,
    )
    second = test_client.post(
        f"/api/mall/orders/{order['order_no']}/payment",
        json={"pay_type": "native"},
        headers=buyer_headers,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["out_trade_no"] == second.json()["out_trade_no"]
    assert first.json()["expires_at"]

    refreshed = test_client.post(
        f"/api/mall/orders/{order['order_no']}/payment/refresh",
        headers=buyer_headers,
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["status"] == "unpaid"


def test_unauthenticated_requests_rejected(test_client):
    resp = test_client.get("/api/mall/cart")
    assert resp.status_code == 401

    resp = test_client.post("/api/mall/orders", json={"address_id": 1, "items": []})
    assert resp.status_code == 401

    resp = test_client.get("/api/mall/seller/shop")
    assert resp.status_code == 401

    resp = test_client.get("/api/mall/admin/shops")
    assert resp.status_code == 401

    # 公开接口无需登录
    resp = test_client.get("/api/mall/goods")
    assert resp.status_code == 200
