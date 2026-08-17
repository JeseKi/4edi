# -*- coding: utf-8 -*-
"""退款/售后端到端测试：仅退款、退货退款、取消/拒绝、幂等、仲裁、超时自动同意。"""

from __future__ import annotations

from datetime import timedelta

from src.server.auth import service as auth_service
from src.server.mall import service as mall_service
from src.server.mall.dao import RefundDAO, WalletDAO, WalletLedgerDAO
from src.server.mall.models import (
    LedgerStatus,
    LedgerType,
    RefundStatus,
    RefundType,
)
from src.server.mall.schemas import OrderOut, RefundOut

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
        json={"name": "退款测试店", "description": "自动化测试店铺"},
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

    resp = test_client.post(
        "/api/mall/seller/goods",
        json={
            "name": "退款测试商品",
            "main_image": "/mall/goods-1.svg",
            "images": ["/mall/goods-1.svg"],
            "detail": "退款测试详情",
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
    return shop_id, goods["id"], sku_id


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


def _create_paid_order(test_client, *, buyer_headers, sku_id, quantity=2):
    """下单并 mock 支付成功。返回 (order_no, out_trade_no)。"""
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
    return order.order_no, out_trade_no


def _apply_refund(test_client, *, buyer_headers, order_no, type="refund_only", reason="不想要了"):
    resp = test_client.post(
        "/api/mall/refunds",
        json={"order_no": order_no, "type": type, "reason": reason},
        headers=buyer_headers,
    )
    assert resp.status_code == 201, resp.text
    return RefundOut.model_validate(resp.json())


# ---------------------------------------------------------------------------
# 仅退款全流程
# ---------------------------------------------------------------------------


def test_refund_only_full_flow(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="rfseller", email="rf-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="rfbuyer", email="rf-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    # 库存 10，下单 2 件后剩 8，销量 2
    def _stock_sales(db):
        from src.server.mall.dao import GoodsDAO, GoodsSkuDAO

        goods = GoodsDAO(db).get(goods_id)
        sku = GoodsSkuDAO(db).get(sku_id)
        return goods.stock, goods.sales, sku.stock

    stock, sales, sku_stock = _stock_sales(test_db_session)
    assert (stock, sales, sku_stock) == (8, 2, 8)

    refund = _apply_refund(
        test_client, buyer_headers=buyer_headers, order_no=order_no
    )
    assert refund.type == RefundType.REFUND_ONLY
    assert refund.status == RefundStatus.PENDING
    assert refund.amount_fen == 19800

    # 订单进入退款中
    resp = test_client.get(f"/api/mall/orders/{order_no}", headers=buyer_headers)
    assert resp.json()["status"] == "refunding"

    # 卖家同意 → mock 通道同步退款成功
    resp = test_client.post(
        f"/api/mall/seller/refunds/{refund.refund_no}/agree",
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    done = RefundOut.model_validate(resp.json())
    assert done.status == RefundStatus.SUCCESS
    assert done.channel == "wechat"
    assert done.channel_refund_id == f"mock-refund-{refund.refund_no}"

    # 订单已退款，库存与销量回补
    resp = test_client.get(f"/api/mall/orders/{order_no}", headers=buyer_headers)
    assert resp.json()["status"] == "refunded"
    assert _stock_sales(test_db_session) == (10, 0, 10)

    # 钱包冻结货款扣回，流水为负
    def _check_wallet(db):
        wallet = WalletDAO(db).get(shop_id)
        assert wallet is not None
        assert wallet.frozen_fen == 0
        assert wallet.available_fen == 0
        ledger_items, _ = WalletLedgerDAO(db).list_by_shop(shop_id, 1, 20)
        assert ledger_items, "应存在退款扣回流水"
        ledger = ledger_items[0]
        assert ledger.entry_type == LedgerType.SALE
        assert ledger.status == LedgerStatus.FROZEN
        assert ledger.amount_fen == -19800
        assert ledger.related_no == order_no

    _check_wallet(test_db_session)

    # 买家售后中心可见
    resp = test_client.get("/api/mall/refunds", headers=buyer_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# 退货退款全流程
# ---------------------------------------------------------------------------


def test_return_refund_full_flow(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="rr-seller", email="rr-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="rr-buyer", email="rr-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    shop_id, goods_id, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    # 卖家发货
    resp = test_client.post(
        f"/api/mall/seller/orders/{order_no}/ship",
        json={"shipping_company": "顺丰速运", "tracking_no": "SF1234567890"},
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text

    # 已发货订单只能退货退款
    resp = test_client.post(
        "/api/mall/refunds",
        json={"order_no": order_no, "type": "refund_only", "reason": "想仅退款"},
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    refund = _apply_refund(
        test_client, buyer_headers=buyer_headers, order_no=order_no, type="return_refund", reason="商品损坏"
    )
    assert refund.status == RefundStatus.PENDING

    # 卖家同意退货 → 等待买家寄回
    resp = test_client.post(
        f"/api/mall/seller/refunds/{refund.refund_no}/agree",
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "returning"

    # 买家填写退货物流
    resp = test_client.post(
        f"/api/mall/refunds/{refund.refund_no}/return-tracking",
        json={"return_tracking_company": "中通快递", "return_tracking_no": "ZT888"},
        headers=buyer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["return_tracking_no"] == "ZT888"

    # 卖家确认收到退货 → mock 退款成功
    resp = test_client.post(
        f"/api/mall/seller/refunds/{refund.refund_no}/confirm-return",
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    done = RefundOut.model_validate(resp.json())
    assert done.status == RefundStatus.SUCCESS
    assert done.return_received_at is not None

    resp = test_client.get(f"/api/mall/orders/{order_no}", headers=buyer_headers)
    assert resp.json()["status"] == "refunded"

    def _check_wallet(db):
        wallet = WalletDAO(db).get(shop_id)
        assert wallet is not None
        assert wallet.frozen_fen == 0

    _check_wallet(test_db_session)


# ---------------------------------------------------------------------------
# 买家取消 / 卖家拒绝 → 订单恢复
# ---------------------------------------------------------------------------


def test_buyer_cancel_refund_restores_order(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="bc-seller", email="bc-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="bc-buyer", email="bc-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    refund = _apply_refund(test_client, buyer_headers=buyer_headers, order_no=order_no)
    resp = test_client.post(
        f"/api/mall/refunds/{refund.refund_no}/cancel", headers=buyer_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    resp = test_client.get(f"/api/mall/orders/{order_no}", headers=buyer_headers)
    assert resp.json()["status"] == "paid"

    # 取消后可重新申请
    refund2 = _apply_refund(test_client, buyer_headers=buyer_headers, order_no=order_no)
    assert refund2.refund_no != refund.refund_no


def test_seller_reject_refund_restores_order(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="sr-seller", email="sr-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="sr-buyer", email="sr-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    refund = _apply_refund(test_client, buyer_headers=buyer_headers, order_no=order_no)
    resp = test_client.post(
        f"/api/mall/seller/refunds/{refund.refund_no}/reject",
        json={"reason": "商品无质量问题"},
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"
    assert resp.json()["refuse_reason"] == "商品无质量问题"

    resp = test_client.get(f"/api/mall/orders/{order_no}", headers=buyer_headers)
    assert resp.json()["status"] == "paid"


# ---------------------------------------------------------------------------
# 校验与幂等
# ---------------------------------------------------------------------------


def test_refund_validation_and_idempotency(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="rv-seller", email="rv-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="rv-buyer", email="rv-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    # 重复申请被拒绝
    refund = _apply_refund(test_client, buyer_headers=buyer_headers, order_no=order_no)
    resp = test_client.post(
        "/api/mall/refunds",
        json={"order_no": order_no, "type": "refund_only", "reason": "再次申请"},
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    # 未支付订单不可申请退款
    resp = test_client.post(
        "/api/mall/orders",
        json={
            "address_id": _add_address(test_client, buyer_headers),
            "items": [{"sku_id": sku_id, "quantity": 1}],
        },
        headers=buyer_headers,
    )
    unpaid_no = resp.json()["order_no"]
    resp = test_client.post(
        "/api/mall/refunds",
        json={"order_no": unpaid_no, "type": "refund_only", "reason": "未支付退款"},
        headers=buyer_headers,
    )
    assert resp.status_code == 400, resp.text

    # 幂等：退款成功后再次同意/回调不改变结果、不重复扣钱
    resp = test_client.post(
        f"/api/mall/seller/refunds/{refund.refund_no}/agree",
        headers=seller_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    resp = test_client.post(
        f"/api/mall/seller/refunds/{refund.refund_no}/agree",
        headers=seller_headers,
    )
    assert resp.status_code == 400, resp.text  # 已处理不可重复同意

    # 直接调用回调入口验证幂等（SUCCESS 短路，不重复回补库存）
    def _idempotent_callback(db):
        mall_service.handle_refund_notification(
            db,
            out_refund_no=refund.refund_no,
            refund_status="SUCCESS",
            channel_refund_id="again",
        )
        from src.server.mall.dao import GoodsSkuDAO

        return GoodsSkuDAO(db).get(sku_id).stock

    stock_after = _idempotent_callback(test_db_session)
    assert stock_after == 9  # 库存未被重复回补（另有 1 件被未支付订单占用）

    # 非本店卖家无权处理
    other_seller_headers = _login(
        test_client,
        username=_register(test_client, username="rv-other", email="rv-other@test.com"),
    )
    resp = test_client.post(
        f"/api/mall/seller/refunds/{refund.refund_no}/agree",
        headers=other_seller_headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# 管理员仲裁
# ---------------------------------------------------------------------------


def test_admin_arbitration(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="ar-seller", email="ar-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="ar-buyer", email="ar-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    refund = _apply_refund(test_client, buyer_headers=buyer_headers, order_no=order_no)

    # 管理员同意 → mock 退款成功
    resp = test_client.get("/api/mall/admin/refunds", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1

    resp = test_client.post(
        f"/api/mall/admin/refunds/{refund.id}/handle",
        json={"approved": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    # 新订单退款申请被管理员驳回 → 订单恢复
    order_no2, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)
    refund2 = _apply_refund(test_client, buyer_headers=buyer_headers, order_no=order_no2)
    resp = test_client.post(
        f"/api/mall/admin/refunds/{refund2.id}/handle",
        json={"approved": False, "reject_reason": "证据不足"},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"

    resp = test_client.get(f"/api/mall/orders/{order_no2}", headers=buyer_headers)
    assert resp.json()["status"] == "paid"


# ---------------------------------------------------------------------------
# 超时自动同意（worker）
# ---------------------------------------------------------------------------


def test_auto_agree_refund_worker(test_client, test_db_session, init_test_database):
    seller_headers = _login(test_client, username=_register(test_client, username="aa-seller", email="aa-seller@test.com"))
    buyer_headers = _login(test_client, username=_register(test_client, username="aa-buyer", email="aa-buyer@test.com"))
    admin_headers = _login_admin(test_client)

    _, _, sku_id = _seed_shop_and_goods(
        test_client, seller_headers=seller_headers, admin_headers=admin_headers
    )
    order_no, _ = _create_paid_order(test_client, buyer_headers=buyer_headers, sku_id=sku_id)

    refund = _apply_refund(test_client, buyer_headers=buyer_headers, order_no=order_no)

    # 未超时：不处理
    mall_service.auto_agree_refund(test_db_session, refund.refund_no)
    assert RefundDAO(test_db_session).get_by_no(refund.refund_no).status == RefundStatus.PENDING

    # 把创建时间改到超时之前
    def _backdate(db):
        item = RefundDAO(db).get_by_no(refund.refund_no)
        item.created_at = item.created_at - timedelta(hours=100)

    _backdate(test_db_session)
    test_db_session.commit()
    mall_service.auto_agree_refund(test_db_session, refund.refund_no)
    assert RefundDAO(test_db_session).get_by_no(refund.refund_no).status == RefundStatus.SUCCESS
    test_db_session.commit()

    # 已成功再触发：幂等
    mall_service.auto_agree_refund(test_db_session, refund.refund_no)
    assert RefundDAO(test_db_session).get_by_no(refund.refund_no).status == RefundStatus.SUCCESS
    test_db_session.commit()

    resp = test_client.get(f"/api/mall/orders/{order_no}", headers=buyer_headers)
    assert resp.json()["status"] == "refunded"
