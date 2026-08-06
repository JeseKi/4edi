# -*- coding: utf-8 -*-
"""商城请求侧服务（短事务）。

所有函数由 HTTP 请求的受控短事务调用。创建订单与持久化支付超时任务、
发货与持久化自动收货任务必须在同一短事务中完成。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.dependencies.current_user import AuthenticatedPrincipal
from src.server.auth.schemas import UserRole
from src.server.task_runtime import TaskReference, TaskRuntime

from ..config import mall_config
from ..dao import (
    AddressDAO,
    CartItemDAO,
    CategoryDAO,
    ChatMessageDAO,
    GoodsDAO,
    GoodsSkuDAO,
    OrderDAO,
    OrderItemDAO,
    OrderLogDAO,
    PaymentDAO,
    ShopDAO,
    WalletDAO,
    WalletLedgerDAO,
    WithdrawRequestDAO,
)
from ..models import (
    Address,
    CartItem,
    Category,
    ChatMessage,
    ChatSenderType,
    Goods,
    GoodsSku,
    GoodsStatus,
    LedgerStatus,
    LedgerType,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Shop,
    ShopStatus,
    Wallet,
    WithdrawRequest,
    WithdrawStatus,
)
from .long_tasks import (
    MALL_ORDER_AUTO_CONFIRM,
    MALL_ORDER_PAYMENT_TIMEOUT,
)

ADMIN_ROLES = frozenset({UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value})


def is_admin_role(role: str) -> bool:
    return role in ADMIN_ROLES


def _gen_business_no(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}{stamp}{secrets.randbelow(1000000):06d}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """把数据库读出的可能 naive 的时间归一化为带时区的 UTC。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# 店铺
# ---------------------------------------------------------------------------


def resolve_seller_shop(db: Session, principal: AuthenticatedPrincipal, shop_id: int | None) -> Shop:
    """卖家操作按主体解析店铺：管理员可传 shop_id 操作任意店铺。"""
    if shop_id is not None:
        if not is_admin_role(principal.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可指定店铺"
            )
        shop = ShopDAO(db).get(shop_id)
        if shop is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
        return shop
    shop = ShopDAO(db).get_by_owner(principal.user_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚未申请店铺")
    return shop


def apply_shop(
    db: Session, principal: AuthenticatedPrincipal, *, name: str, description: str | None, avatar: str | None
) -> Shop:
    shop_dao = ShopDAO(db)
    existing = shop_dao.get_by_owner(principal.user_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已申请过店铺")
    try:
        return shop_dao.create(
            owner_user_id=principal.user_id, name=name, description=description, avatar=avatar
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def get_my_shop(db: Session, principal: AuthenticatedPrincipal) -> Shop:
    shop = ShopDAO(db).get_by_owner(principal.user_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="尚未申请店铺")
    return shop


def get_public_shop(db: Session, shop_id: int) -> Shop:
    shop = ShopDAO(db).get(shop_id)
    if shop is None or shop.status != ShopStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
    return shop


def update_shop(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    name: str | None,
    description: str | None,
    avatar: str | None,
    shop_id: int | None = None,
) -> Shop:
    shop = resolve_seller_shop(db, principal, shop_id)
    if shop.status != ShopStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="店铺未通过审核")
    if name is not None:
        shop.name = name
    if description is not None:
        shop.description = description
    if avatar is not None:
        shop.avatar = avatar
    return shop


def admin_list_shops(
    db: Session,
    *,
    status_filter: ShopStatus | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Shop], int]:
    return ShopDAO(db).list(status=status_filter, keyword=keyword, page=page, page_size=page_size)


def admin_review_shop(
    db: Session, shop_id: int, *, approved: bool, reject_reason: str | None, handler_user_id: int
) -> Shop:
    shop = ShopDAO(db).lock(shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
    if shop.status not in (ShopStatus.PENDING, ShopStatus.REJECTED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="店铺不是待审核状态")
    if approved:
        shop.status = ShopStatus.APPROVED
        shop.approved_at = _utcnow()
        shop.reject_reason = None
        shop.deposit_fen = mall_config.default_deposit_fen
        wallet = WalletDAO(db).get_or_create(shop.id)
        wallet.deposit_fen = mall_config.default_deposit_fen
        if mall_config.default_deposit_fen > 0:
            WalletLedgerDAO(db).create(
                shop_id=shop.id,
                entry_type=LedgerType.DEPOSIT,
                status=LedgerStatus.WITHDRAWN,
                amount_fen=-mall_config.default_deposit_fen,
                note="入驻保证金",
            )
    else:
        shop.status = ShopStatus.REJECTED
        shop.reject_reason = reject_reason or "资料不完整"
    return shop


def admin_close_shop(db: Session, shop_id: int) -> Shop:
    shop = ShopDAO(db).lock(shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
    if shop.status != ShopStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅可关闭已审核店铺")
    shop.status = ShopStatus.CLOSED
    shop.closed_at = _utcnow()
    db.query(Goods).filter(Goods.shop_id == shop_id, Goods.status == GoodsStatus.ON).update(
        {Goods.status: GoodsStatus.OFF}, synchronize_session=False
    )
    return shop


# ---------------------------------------------------------------------------
# 分类与商品（买家侧）
# ---------------------------------------------------------------------------


def list_categories(db: Session) -> list[Category]:
    return CategoryDAO(db).list_all()


def create_category(
    db: Session, *, name: str, parent_id: int | None, sort: int, icon: str | None
) -> Category:
    try:
        return CategoryDAO(db).create(name=name, parent_id=parent_id, sort=sort, icon=icon)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def search_goods(
    db: Session,
    *,
    keyword: str | None,
    category_id: int | None,
    shop_id: int | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[Goods], int]:
    return GoodsDAO(db).list_public(
        keyword=keyword,
        category_id=category_id,
        shop_id=shop_id,
        sort=sort,
        page=page,
        page_size=page_size,
    )


def get_goods_detail(db: Session, goods_id: int) -> tuple[Goods, list[GoodsSku], Shop]:
    goods = GoodsDAO(db).get(goods_id)
    if goods is None or goods.deleted_at is not None or goods.status != GoodsStatus.ON:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架")
    shop = ShopDAO(db).get(goods.shop_id)
    if shop is None or shop.status != ShopStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架")
    skus = GoodsSkuDAO(db).list_by_goods(goods.id)
    return goods, skus, shop


# ---------------------------------------------------------------------------
# 卖家商品管理
# ---------------------------------------------------------------------------


def _apply_skus(db: Session, goods: Goods, skus_data: list[dict]) -> None:
    sku_dao = GoodsSkuDAO(db)
    sku_dao.delete_by_goods(goods.id)
    prices: list[int] = []
    total_stock = 0
    for data in skus_data:
        price = int(data["price_fen"])
        stock = int(data["stock"])
        prices.append(price)
        total_stock += stock
        sku_dao.create(
            goods_id=goods.id,
            sku_code=data.get("sku_code"),
            specs=data.get("specs") or {},
            price_fen=price,
            stock=stock,
        )
    goods.price_fen = min(prices) if prices else 0
    goods.stock = total_stock


def create_goods(
    db: Session, principal: AuthenticatedPrincipal, payload: dict, *, shop_id: int | None = None
) -> Goods:
    shop = resolve_seller_shop(db, principal, shop_id)
    if shop.status != ShopStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="店铺未通过审核")
    goods = GoodsDAO(db).create(
        shop_id=shop.id,
        category_id=payload.get("category_id"),
        name=payload["name"],
        main_image=payload["main_image"],
        images=payload.get("images") or [],
        detail=payload.get("detail"),
        price_fen=0,
        original_price_fen=payload.get("original_price_fen"),
        stock=0,
    )
    _apply_skus(db, goods, payload["skus"])
    return goods


def get_shop_goods(db: Session, principal: AuthenticatedPrincipal, goods_id: int, *, shop_id: int | None = None) -> Goods:
    shop = resolve_seller_shop(db, principal, shop_id)
    goods = GoodsDAO(db).get(goods_id)
    if goods is None or goods.deleted_at is not None or goods.shop_id != shop.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return goods


def get_goods_skus(db: Session, goods_id: int) -> list[GoodsSku]:
    return GoodsSkuDAO(db).list_by_goods(goods_id)


def get_shop_record(db: Session, shop_id: int) -> Shop:
    shop = ShopDAO(db).get(shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
    return shop


def list_shop_goods(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    status_filter: GoodsStatus | None,
    keyword: str | None,
    page: int,
    page_size: int,
    shop_id: int | None = None,
) -> tuple[list[Goods], int]:
    shop = resolve_seller_shop(db, principal, shop_id)
    return GoodsDAO(db).list_for_shop(
        shop_id=shop.id, status=status_filter, keyword=keyword, page=page, page_size=page_size
    )


def update_goods(
    db: Session, principal: AuthenticatedPrincipal, goods_id: int, payload: dict, *, shop_id: int | None = None
) -> Goods:
    goods = get_shop_goods(db, principal, goods_id, shop_id=shop_id)
    for field in ("category_id", "name", "main_image", "images", "detail", "original_price_fen"):
        if field in payload:
            setattr(goods, field, payload[field])
    if payload.get("skus") is not None:
        _apply_skus(db, goods, payload["skus"])
    return goods


def set_goods_status(
    db: Session, principal: AuthenticatedPrincipal, goods_id: int, *, on: bool, shop_id: int | None = None
) -> Goods:
    goods = get_shop_goods(db, principal, goods_id, shop_id=shop_id)
    if on:
        if goods.stock <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品库存不能为 0")
        goods.status = GoodsStatus.ON
    else:
        goods.status = GoodsStatus.OFF
    return goods


def delete_goods(db: Session, principal: AuthenticatedPrincipal, goods_id: int, *, shop_id: int | None = None) -> None:
    goods = get_shop_goods(db, principal, goods_id, shop_id=shop_id)
    goods.deleted_at = _utcnow()
    goods.status = GoodsStatus.OFF


# ---------------------------------------------------------------------------
# 购物车
# ---------------------------------------------------------------------------


def add_cart_item(
    db: Session, user_id: int, *, goods_id: int, sku_id: int, quantity: int
) -> CartItem:
    goods = GoodsDAO(db).get(goods_id)
    if goods is None or goods.deleted_at is not None or goods.status != GoodsStatus.ON:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品已下架")
    sku = GoodsSkuDAO(db).get(sku_id)
    if sku is None or sku.goods_id != goods_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SKU 不存在")
    if sku.stock < quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足")
    return CartItemDAO(db).add_or_update(
        user_id=user_id, goods_id=goods_id, sku_id=sku_id, quantity=quantity
    )


def list_cart(db: Session, user_id: int) -> list[dict]:
    items = CartItemDAO(db).list_for_user(user_id)
    result: list[dict] = []
    for item in items:
        goods = GoodsDAO(db).get(item.goods_id)
        if goods is None:
            continue
        sku = GoodsSkuDAO(db).get(item.sku_id)
        shop = ShopDAO(db).get(goods.shop_id)
        result.append(
            {
                "id": item.id,
                "goods_id": item.goods_id,
                "sku_id": item.sku_id,
                "quantity": item.quantity,
                "selected": item.selected,
                "shop_id": goods.shop_id,
                "shop_name": shop.name if shop else "",
                "goods_name": goods.name,
                "goods_image": goods.main_image,
                "sku_specs": sku.specs if sku else {},
                "price_fen": sku.price_fen if sku else 0,
                "subtotal_fen": (sku.price_fen if sku else 0) * item.quantity,
                "stock": sku.stock if sku else 0,
                "goods_on": goods.status == GoodsStatus.ON and goods.deleted_at is None,
            }
        )
    return result


def update_cart_item(
    db: Session, user_id: int, item_id: int, *, quantity: int | None, selected: bool | None
) -> CartItem:
    item = CartItemDAO(db).get_for_user(item_id, user_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在")
    if quantity is not None:
        sku = GoodsSkuDAO(db).get(item.sku_id)
        if sku is None or sku.stock < quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足")
        item.quantity = quantity
    if selected is not None:
        item.selected = selected
    return item


def delete_cart_items(db: Session, user_id: int, item_ids: list[int]) -> int:
    return CartItemDAO(db).delete_for_user(item_ids, user_id)


# ---------------------------------------------------------------------------
# 收货地址
# ---------------------------------------------------------------------------


def create_address(db: Session, user_id: int, payload: dict) -> Address:
    address_dao = AddressDAO(db)
    if payload.get("is_default"):
        address_dao.clear_default(user_id)
    return address_dao.create(user_id=user_id, **payload)


def list_addresses(db: Session, user_id: int) -> list[Address]:
    return AddressDAO(db).list_for_user(user_id)


def get_address_for_user(db: Session, user_id: int, address_id: int) -> Address:
    address = AddressDAO(db).get_for_user(address_id, user_id)
    if address is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    return address


def update_address(db: Session, user_id: int, address_id: int, payload: dict) -> Address:
    address = get_address_for_user(db, user_id, address_id)
    address_dao = AddressDAO(db)
    if payload.get("is_default") and not address.is_default:
        address_dao.clear_default(user_id)
    for field in ("receiver", "phone", "province", "city", "district", "detail", "is_default"):
        if field in payload:
            setattr(address, field, payload[field])
    return address


def delete_address(db: Session, user_id: int, address_id: int) -> None:
    if not AddressDAO(db).delete_for_user(address_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")


# ---------------------------------------------------------------------------
# 订单
# ---------------------------------------------------------------------------


def _validate_order_items(db: Session, items: list[dict]) -> tuple[int, list[dict]]:
    """校验 SKU 并锁定库存行，返回 shop_id 与组装好的订单条目。"""
    sku_ids = [int(item["sku_id"]) for item in items]
    if len(set(sku_ids)) != len(sku_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="同一商品不能重复下单")
    goods_dao = GoodsDAO(db)
    sku_dao = GoodsSkuDAO(db)
    shop_id: int | None = None
    order_items: list[dict] = []
    for item in items:
        sku = sku_dao.lock(item["sku_id"])
        if sku is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="商品 SKU 不存在")
        goods = goods_dao.lock(sku.goods_id)
        if (
            goods is None
            or goods.deleted_at is not None
            or goods.status != GoodsStatus.ON
        ):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"商品「{goods.name if goods else ''}」已下架")
        if shop_id is None:
            shop_id = goods.shop_id
        elif goods.shop_id != shop_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="暂不支持跨店结算")
        quantity = int(item["quantity"])
        if sku.stock < quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"商品「{goods.name}」库存不足")
        order_items.append(
            {
                "goods_id": goods.id,
                "sku_id": sku.id,
                "goods_name": goods.name,
                "goods_image": goods.main_image,
                "sku_specs": sku.specs,
                "unit_price_fen": sku.price_fen,
                "quantity": quantity,
                "subtotal_fen": sku.price_fen * quantity,
                "stock": sku.stock,
            }
        )
    if shop_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订单商品为空")
    return shop_id, order_items


def _deduct_stock(db: Session, order_items: list[dict]) -> None:
    sku_dao = GoodsSkuDAO(db)
    goods_dao = GoodsDAO(db)
    for item in order_items:
        sku = sku_dao.lock(item["sku_id"])
        if sku is None or sku.stock < item["quantity"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="库存不足")
        sku.stock -= item["quantity"]
        goods = goods_dao.lock(item["goods_id"])
        if goods is not None:
            goods.stock = max(goods.stock - item["quantity"], 0)


def _restore_stock(db: Session, order_items: list[dict]) -> None:
    sku_dao = GoodsSkuDAO(db)
    goods_dao = GoodsDAO(db)
    for item in order_items:
        sku = sku_dao.lock(item["sku_id"])
        if sku is not None:
            sku.stock += item["quantity"]
        goods = goods_dao.lock(item["goods_id"])
        if goods is not None:
            goods.stock += item["quantity"]


def preview_order(db: Session, user_id: int, items: list[dict]) -> dict:
    del user_id  # 预览不依赖买家
    shop_id, order_items = _validate_order_items(db, items)
    del shop_id
    goods_amount = sum(item["subtotal_fen"] for item in order_items)
    freight = mall_config.freight_fen
    return {
        "items": order_items,
        "goods_amount_fen": goods_amount,
        "freight_fen": freight,
        "pay_amount_fen": goods_amount + freight,
    }


def create_order(
    db: Session,
    runtime: TaskRuntime,
    *,
    user_id: int,
    address_id: int,
    items: list[dict],
    cart_item_ids: list[int],
    remark: str | None,
) -> Order:
    address = get_address_for_user(db, user_id, address_id)
    shop_id, order_items = _validate_order_items(db, items)
    goods_amount = sum(item["subtotal_fen"] for item in order_items)
    freight = mall_config.freight_fen
    pay_amount = goods_amount + freight

    order = OrderDAO(db).create(
        order_no=_gen_business_no("M"),
        buyer_id=user_id,
        shop_id=shop_id,
        goods_amount_fen=goods_amount,
        freight_fen=freight,
        pay_amount_fen=pay_amount,
        receiver_name=address.receiver,
        receiver_phone=address.phone,
        receiver_address=f"{address.province}{address.city}{address.district}{address.detail}",
        remark=remark,
    )
    item_dao = OrderItemDAO(db)
    for item in order_items:
        item_dao.create_many(
            order_id=order.id,
            goods_id=item["goods_id"],
            sku_id=item["sku_id"],
            goods_name=item["goods_name"],
            goods_image=item["goods_image"],
            sku_specs=item["sku_specs"],
            unit_price_fen=item["unit_price_fen"],
            quantity=item["quantity"],
            subtotal_fen=item["subtotal_fen"],
        )
    _deduct_stock(db, order_items)
    if cart_item_ids:
        CartItemDAO(db).delete_for_user(cart_item_ids, user_id)
    OrderLogDAO(db).append(order.id, "订单创建成功，等待买家付款")
    runtime.enqueue(
        db,
        MALL_ORDER_PAYMENT_TIMEOUT,
        order.order_no,
        reference=TaskReference(resource_type="mall_order", resource_id=order.order_no),
        not_before=_utcnow() + timedelta(minutes=mall_config.order_pay_timeout_minutes),
    )
    return order


def _get_order_for_buyer(db: Session, user_id: int, order_no: str) -> Order:
    order = OrderDAO(db).get_for_buyer(order_no, user_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


def cancel_order(db: Session, user_id: int, order_no: str) -> Order:
    order = OrderDAO(db).lock_by_no(order_no)
    if order is None or order.buyer_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅未支付订单可取消")
    _do_cancel(db, order, "买家主动取消")
    return order


def cancel_expired_order(db: Session, order_no: str) -> None:
    """支付超时任务调用；幂等，仅取消未支付且已超时的订单。"""
    order = OrderDAO(db).lock_by_no(order_no)
    if order is None or order.status != OrderStatus.PENDING_PAYMENT:
        return
    deadline = order.created_at + timedelta(minutes=mall_config.order_pay_timeout_minutes)
    if _utcnow() < _as_utc(deadline):
        return
    _do_cancel(db, order, "支付超时，系统自动取消")


def _do_cancel(db: Session, order: Order, reason: str) -> None:
    items = OrderItemDAO(db).list_by_order(order.id)
    item_snapshots = [
        {"sku_id": item.sku_id, "goods_id": item.goods_id, "quantity": item.quantity}
        for item in items
    ]
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = _utcnow()
    order.cancel_reason = reason
    _restore_stock(db, item_snapshots)
    OrderLogDAO(db).append(order.id, f"订单已取消：{reason}")


def list_my_orders(
    db: Session, user_id: int, status_filter: OrderStatus | None, page: int, page_size: int
) -> tuple[list[Order], int]:
    return OrderDAO(db).list_for_buyer(user_id, status_filter, page, page_size)


def get_my_order(db: Session, user_id: int, order_no: str) -> Order:
    return _get_order_for_buyer(db, user_id, order_no)


def confirm_receipt(db: Session, user_id: int, order_no: str) -> Order:
    order = _get_order_for_buyer(db, user_id, order_no)
    return confirm_receipt_by_no(db, order.order_no)


def confirm_receipt_by_no(db: Session, order_no: str) -> Order:
    """确认收货：解冻货款到可用余额；幂等。"""
    order = OrderDAO(db).lock_by_no(order_no)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.status not in (OrderStatus.PAID, OrderStatus.SHIPPED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前订单状态不可确认收货")
    order.status = OrderStatus.COMPLETED
    order.completed_at = _utcnow()
    if order.shipping_traces:
        traces = list(order.shipping_traces)
        traces.append(
            {"time": order.completed_at.isoformat(), "text": "已签收，订单完成"}
        )
        order.shipping_traces = traces
    wallet = WalletDAO(db).get_or_create(order.shop_id)
    wallet.frozen_fen = max(wallet.frozen_fen - order.pay_amount_fen, 0)
    wallet.available_fen += order.pay_amount_fen
    WalletLedgerDAO(db).create(
        shop_id=order.shop_id,
        entry_type=LedgerType.SALE,
        status=LedgerStatus.AVAILABLE,
        amount_fen=order.pay_amount_fen,
        related_no=order.order_no,
        note="确认收货，货款解冻",
        available_at=_utcnow(),
    )
    OrderLogDAO(db).append(order.id, "买家确认收货，货款已解冻至商家余额")
    return order


def auto_confirm_order(db: Session, order_no: str) -> None:
    """自动确认收货任务调用；幂等。"""
    order = OrderDAO(db).lock_by_no(order_no)
    if order is None or order.status != OrderStatus.SHIPPED:
        return
    if order.shipped_at is not None:
        deadline = order.shipped_at + timedelta(days=mall_config.auto_confirm_receipt_days)
        if _utcnow() < _as_utc(deadline):
            return
    order = confirm_receipt_by_no(db, order_no)
    OrderLogDAO(db).append(order.id, "超时未确认，系统自动确认收货")


def order_detail_payload(db: Session, order: Order) -> dict:
    items = OrderItemDAO(db).list_by_order(order.id)
    logs = OrderLogDAO(db).list_by_order(order.id)
    shop = ShopDAO(db).get(order.shop_id)
    return {
        "id": order.id,
        "order_no": order.order_no,
        "buyer_id": order.buyer_id,
        "shop_id": order.shop_id,
        "status": order.status,
        "goods_amount_fen": order.goods_amount_fen,
        "freight_fen": order.freight_fen,
        "pay_amount_fen": order.pay_amount_fen,
        "receiver_name": order.receiver_name,
        "receiver_phone": order.receiver_phone,
        "receiver_address": order.receiver_address,
        "remark": order.remark,
        "shipping_company": order.shipping_company,
        "tracking_no": order.tracking_no,
        "shipping_traces": order.shipping_traces,
        "payment_channel": order.payment_channel,
        "payment_type": order.payment_type,
        "paid_at": order.paid_at,
        "shipped_at": order.shipped_at,
        "completed_at": order.completed_at,
        "cancelled_at": order.cancelled_at,
        "cancel_reason": order.cancel_reason,
        "created_at": order.created_at,
        "shop_name": shop.name if shop else None,
        "items": [
            {
                "id": item.id,
                "order_id": item.order_id,
                "goods_id": item.goods_id,
                "sku_id": item.sku_id,
                "goods_name": item.goods_name,
                "goods_image": item.goods_image,
                "sku_specs": item.sku_specs,
                "unit_price_fen": item.unit_price_fen,
                "quantity": item.quantity,
                "subtotal_fen": item.subtotal_fen,
            }
            for item in items
        ],
        "logs": [
            {
                "id": log.id,
                "order_id": log.order_id,
                "message": log.message,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }


def order_list_payloads(db: Session, orders: list[Order]) -> list[dict]:
    return [order_detail_payload(db, order) for order in orders]


# ---------------------------------------------------------------------------
# 支付
# ---------------------------------------------------------------------------


def create_payment(
    db: Session, user_id: int, order_no: str, *, pay_type: str
) -> Payment:
    order = _get_order_for_buyer(db, user_id, order_no)
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前订单不可支付")
    from ..payment import get_payment_provider

    provider = get_payment_provider()
    payment = PaymentDAO(db).create(
        out_trade_no=_gen_business_no("P"),
        order_no=order.order_no,
        amount_fen=order.pay_amount_fen,
        channel=provider.key,
        pay_type=pay_type,
    )
    notify_url = _resolve_notify_url()
    try:
        prepay = provider.create_prepay(
            out_trade_no=payment.out_trade_no,
            amount_fen=payment.amount_fen,
            description=order.receiver_name,
            pay_type=pay_type,
            notify_url=notify_url,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"支付下单失败：{exc}"
        )
    payment.prepay_id = prepay.prepay_id
    payment.code_url = prepay.code_url
    return payment


def _resolve_notify_url() -> str:
    from src.server.mall.payment.service import _resolve_notify_url

    return _resolve_notify_url()


def get_payment_for_buyer(db: Session, user_id: int, order_no: str) -> Payment:
    order = _get_order_for_buyer(db, user_id, order_no)
    payment = PaymentDAO(db).get_by_order_no(order.order_no)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    return payment


def mark_paid(
    db: Session,
    *,
    out_trade_no: str,
    transaction_id: str | None,
    paid_at: datetime | None = None,
) -> Payment:
    """支付成功入账：订单置为已支付，货款冻结到店铺钱包；幂等。"""
    payment = PaymentDAO(db).get_by_out_trade_no(out_trade_no)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    if payment.status == PaymentStatus.SUCCESS:
        return payment
    order = OrderDAO(db).lock_by_no(payment.order_no)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="订单已关闭，支付无效"
        )
    paid_at = paid_at or _utcnow()
    payment.status = PaymentStatus.SUCCESS
    payment.transaction_id = transaction_id or f"mock-{out_trade_no}"
    payment.paid_at = paid_at
    order.status = OrderStatus.PAID
    order.paid_at = paid_at
    order.payment_channel = payment.channel
    order.payment_type = payment.pay_type
    for item in OrderItemDAO(db).list_by_order(order.id):
        goods = GoodsDAO(db).lock(item.goods_id)
        if goods is not None:
            goods.sales += item.quantity
    wallet = WalletDAO(db).get_or_create(order.shop_id)
    wallet.frozen_fen += payment.amount_fen
    WalletLedgerDAO(db).create(
        shop_id=order.shop_id,
        entry_type=LedgerType.SALE,
        status=LedgerStatus.FROZEN,
        amount_fen=payment.amount_fen,
        related_no=order.order_no,
        note="订单支付，货款冻结",
    )
    OrderLogDAO(db).append(order.id, "支付成功，货款已冻结，等待卖家发货")
    return payment


def handle_payment_notification(
    db: Session, *, out_trade_no: str, transaction_id: str | None
) -> Payment:
    """支付回调入口（微信通知 / mock 支付共用），同一短事务内完成入账。"""
    return mark_paid(db, out_trade_no=out_trade_no, transaction_id=transaction_id)


def query_payment_status(db: Session, user_id: int, order_no: str) -> dict:
    payment = get_payment_for_buyer(db, user_id, order_no)
    from ..payment import get_payment_provider

    provider = get_payment_provider()
    if provider.is_mock:
        return {
            "out_trade_no": payment.out_trade_no,
            "status": payment.status.value,
            "paid": payment.status == PaymentStatus.SUCCESS,
        }
    result = provider.query_order(out_trade_no=payment.out_trade_no)
    return {
        "out_trade_no": payment.out_trade_no,
        "status": payment.status.value,
        "paid": payment.status == PaymentStatus.SUCCESS or result.paid,
    }


# ---------------------------------------------------------------------------
# 卖家订单与发货
# ---------------------------------------------------------------------------


def list_shop_orders(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    status_filter: OrderStatus | None,
    page: int,
    page_size: int,
    shop_id: int | None = None,
) -> tuple[list[Order], int]:
    shop = resolve_seller_shop(db, principal, shop_id)
    return OrderDAO(db).list_for_shop(shop.id, status_filter, page, page_size)


def get_shop_order(
    db: Session, principal: AuthenticatedPrincipal, order_no: str, *, shop_id: int | None = None
) -> Order:
    shop = resolve_seller_shop(db, principal, shop_id)
    order = OrderDAO(db).get_for_shop(order_no, shop.id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


def ship_order(
    db: Session,
    runtime: TaskRuntime,
    principal: AuthenticatedPrincipal,
    order_no: str,
    *,
    shipping_company: str,
    tracking_no: str,
    shop_id: int | None = None,
) -> Order:
    order = get_shop_order(db, principal, order_no, shop_id=shop_id)
    if order.status != OrderStatus.PAID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅已支付订单可发货")
    now = _utcnow()
    order.status = OrderStatus.SHIPPED
    order.shipped_at = now
    order.shipping_company = shipping_company
    order.tracking_no = tracking_no
    order.shipping_traces = [
        {"time": now.isoformat(), "text": "商家已发货，商品已揽收"},
        {
            "time": (now + timedelta(hours=12)).isoformat(),
            "text": "快件已到达转运中心，正在发往目的地",
        },
        {"time": (now + timedelta(hours=30)).isoformat(), "text": "派送中，快递员正在派件"},
    ]
    OrderLogDAO(db).append(order.id, f"商家已发货：{shipping_company} {tracking_no}")
    runtime.enqueue(
        db,
        MALL_ORDER_AUTO_CONFIRM,
        order.order_no,
        reference=TaskReference(resource_type="mall_order", resource_id=order.order_no),
        not_before=now + timedelta(days=mall_config.auto_confirm_receipt_days),
    )
    return order


# ---------------------------------------------------------------------------
# 钱包与提现
# ---------------------------------------------------------------------------


def get_shop_wallet(db: Session, principal: AuthenticatedPrincipal, *, shop_id: int | None = None) -> Wallet:
    shop = resolve_seller_shop(db, principal, shop_id)
    wallet = WalletDAO(db).get(shop.id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺钱包不存在")
    return wallet


def wallet_out(wallet: Wallet) -> dict:
    return {
        "shop_id": wallet.shop_id,
        "available_fen": wallet.available_fen,
        "frozen_fen": wallet.frozen_fen,
        "deposit_fen": wallet.deposit_fen,
        "total_fen": wallet.available_fen + wallet.frozen_fen + wallet.deposit_fen,
    }


def list_wallet_ledger(
    db: Session, principal: AuthenticatedPrincipal, *, page: int, page_size: int, shop_id: int | None = None
) -> tuple[list, int]:
    shop = resolve_seller_shop(db, principal, shop_id)
    return WalletLedgerDAO(db).list_by_shop(shop.id, page, page_size)


def request_withdraw(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    amount_fen: int,
    account_info: dict,
    shop_id: int | None = None,
) -> WithdrawRequest:
    shop = resolve_seller_shop(db, principal, shop_id)
    wallet = WalletDAO(db).lock(shop.id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺钱包不存在")
    if wallet.available_fen < amount_fen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="可提现余额不足")
    wallet.available_fen -= amount_fen
    WalletLedgerDAO(db).create(
        shop_id=shop.id,
        entry_type=LedgerType.WITHDRAW,
        status=LedgerStatus.WITHDRAWN,
        amount_fen=-amount_fen,
        note="提现申请",
    )
    request = WithdrawRequestDAO(db).create(
        shop_id=shop.id,
        withdraw_no=_gen_business_no("W"),
        amount_fen=amount_fen,
        account_info=account_info,
    )
    return request


def list_my_withdrawals(
    db: Session, principal: AuthenticatedPrincipal, *, page: int, page_size: int, shop_id: int | None = None
) -> tuple[list[WithdrawRequest], int]:
    shop = resolve_seller_shop(db, principal, shop_id)
    return WithdrawRequestDAO(db).list_by_shop(shop.id, page, page_size)


def admin_list_withdrawals(
    db: Session, *, status_filter: WithdrawStatus | None, page: int, page_size: int
) -> tuple[list[WithdrawRequest], int]:
    return WithdrawRequestDAO(db).list_all(status_filter, page, page_size)


def admin_handle_withdraw(
    db: Session, withdraw_id: int, *, approved: bool, reject_reason: str | None, handler_user_id: int
) -> WithdrawRequest:
    request = WithdrawRequestDAO(db).lock(withdraw_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提现申请不存在")
    if request.status != WithdrawStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="提现申请已处理")
    request.handler_user_id = handler_user_id
    request.handled_at = _utcnow()
    if approved:
        request.status = WithdrawStatus.PAID
    else:
        request.status = WithdrawStatus.REJECTED
        request.reject_reason = reject_reason or "资料不符"
        wallet = WalletDAO(db).lock(request.shop_id)
        if wallet is not None:
            wallet.available_fen += request.amount_fen
        WalletLedgerDAO(db).create(
            shop_id=request.shop_id,
            entry_type=LedgerType.WITHDRAW,
            status=LedgerStatus.AVAILABLE,
            amount_fen=request.amount_fen,
            related_no=request.withdraw_no,
            note="提现驳回退回",
            available_at=_utcnow(),
        )
    return request


# ---------------------------------------------------------------------------
# 客服消息
# ---------------------------------------------------------------------------


def send_buyer_message(
    db: Session, user_id: int, *, shop_id: int, order_no: str | None, content: str
) -> ChatMessage:
    shop = ShopDAO(db).get(shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
    return ChatMessageDAO(db).create(
        shop_id=shop_id,
        order_no=order_no,
        sender_type=ChatSenderType.BUYER,
        sender_user_id=user_id,
        content=content,
    )


def send_seller_message(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    shop_id: int,
    order_no: str | None,
    content: str,
    target_shop_id: int | None = None,
) -> ChatMessage:
    shop = resolve_seller_shop(db, principal, target_shop_id)
    if shop.id != shop_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权在该店铺回复")
    return ChatMessageDAO(db).create(
        shop_id=shop.id,
        order_no=order_no,
        sender_type=ChatSenderType.SELLER,
        sender_user_id=principal.user_id,
        content=content,
    )


def list_buyer_messages(
    db: Session, user_id: int, *, shop_id: int, order_no: str | None, after_id: int | None
) -> list[ChatMessage]:
    dao = ChatMessageDAO(db)
    messages = dao.list_for_buyer(user_id, shop_id, order_no=order_no, after_id=after_id)
    dao.mark_buyer_messages_read(
        shop_id=shop_id, owner_user_id=user_id, order_no=order_no, after_id=after_id
    )
    return messages


def list_seller_messages(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    shop_id: int,
    order_no: str | None,
    after_id: int | None,
    target_shop_id: int | None = None,
) -> list[ChatMessage]:
    shop = resolve_seller_shop(db, principal, target_shop_id)
    if shop.id != shop_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该店铺消息")
    messages = ChatMessageDAO(db).list_for_shop(shop.id, order_no=order_no, after_id=after_id)
    ChatMessageDAO(db).mark_shop_messages_read(shop.id, owner_user_id=principal.user_id, order_no=order_no)
    return messages


def list_buyer_conversations(db: Session, user_id: int) -> list[dict]:
    dao = ChatMessageDAO(db)
    shop_ids = dao.list_shop_ids_for_buyer(user_id)
    result: list[dict] = []
    for shop_id in shop_ids:
        messages = dao.list_for_buyer(user_id, shop_id, order_no=None, after_id=None)
        unread = sum(
            1
            for m in messages
            if m.sender_type == ChatSenderType.SELLER and m.read_at is None
        )
        shop = ShopDAO(db).get(shop_id)
        result.append(
            {
                "shop_id": shop_id,
                "shop_name": shop.name if shop else "",
                "order_no": None,
                "last_message": messages[-1].content if messages else "",
                "last_message_at": messages[-1].created_at if messages else None,
                "unread_count": unread,
            }
        )
    return result


def list_seller_conversations(
    db: Session, principal: AuthenticatedPrincipal, *, target_shop_id: int | None = None
) -> list[dict]:
    shop = resolve_seller_shop(db, principal, target_shop_id)
    rows = (
        db.query(ChatMessage.sender_user_id, ChatMessage.order_no)
        .filter(
            ChatMessage.shop_id == shop.id,
            ChatMessage.sender_type == ChatSenderType.BUYER,
            ChatMessage.sender_user_id.isnot(None),
        )
        .distinct()
        .all()
    )
    result: list[dict] = []
    for sender_user_id, order_no in rows:
        messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.shop_id == shop.id,
                ChatMessage.sender_user_id == sender_user_id,
                ChatMessage.order_no == order_no,
            )
            .order_by(ChatMessage.id.asc())
            .all()
        )
        unread = sum(1 for m in messages if m.sender_type == ChatSenderType.BUYER and m.read_at is None)
        result.append(
            {
                "shop_id": shop.id,
                "shop_name": shop.name,
                "buyer_user_id": sender_user_id,
                "order_no": order_no,
                "last_message": messages[-1].content if messages else "",
                "last_message_at": messages[-1].created_at if messages else None,
                "unread_count": unread,
            }
        )
    result.sort(key=lambda item: item["last_message_at"] or _utcnow(), reverse=True)
    return result
