# -*- coding: utf-8 -*-
"""商城请求侧服务（短事务）。

所有函数由 HTTP 请求的受控短事务调用。创建订单与持久化支付超时任务、
发货与持久化自动收货任务必须在同一短事务中完成。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from loguru import logger
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
    CouponTemplateDAO,
    EvaluationDAO,
    FavoriteDAO,
    FootprintDAO,
    GoodsDAO,
    GoodsSkuDAO,
    OrderDAO,
    OrderItemDAO,
    OrderLogDAO,
    PaymentDAO,
    RefundDAO,
    ShopDAO,
    UserCouponDAO,
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
    CouponScope,
    CouponStatus,
    CouponTemplate,
    CouponType,
    Evaluation,
    Favorite,
    FavoriteTargetType,
    Footprint,
    Goods,
    GoodsSku,
    GoodsStatus,
    LedgerStatus,
    LedgerType,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Refund,
    RefundStatus,
    RefundType,
    Shop,
    ShopStatus,
    UserCoupon,
    UserCouponStatus,
    Wallet,
    WithdrawRequest,
    WithdrawStatus,
)
from .long_tasks import (
    MALL_ORDER_AUTO_CONFIRM,
    MALL_ORDER_PAYMENT_TIMEOUT,
    MALL_REFUND_AUTO_AGREE,
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
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    name: str,
    description: str | None,
    avatar: str | None,
    real_name: str,
    identity_number: str,
    business_license_asset_id: str,
    identity_front_asset_id: str,
    identity_back_asset_id: str,
) -> Shop:
    shop_dao = ShopDAO(db)
    existing = shop_dao.get_by_owner(principal.user_id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已申请过店铺")
    try:
        return shop_dao.create(
            owner_user_id=principal.user_id,
            name=name,
            description=description,
            avatar=avatar,
            real_name=real_name,
            identity_number=identity_number,
            business_license_asset_id=business_license_asset_id,
            identity_front_asset_id=identity_front_asset_id,
            identity_back_asset_id=identity_back_asset_id,
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


def admin_reopen_shop(db: Session, shop_id: int) -> Shop:
    """恢复已关闭店铺的经营资格；商品保持下架，需商家自行确认后上架。"""
    shop = ShopDAO(db).lock(shop_id)
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在")
    if shop.status != ShopStatus.CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅可开启已关闭店铺")
    shop.status = ShopStatus.APPROVED
    shop.closed_at = None
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


def preview_order(
    db: Session, user_id: int, items: list[dict], *, coupon_id: int | None = None
) -> dict:
    shop_id, order_items = _validate_order_items(db, items)
    goods_amount = sum(item["subtotal_fen"] for item in order_items)
    freight = mall_config.freight_fen
    coupon_discount = 0
    if coupon_id is not None:
        coupon_discount = _validate_user_coupon(
            db, user_id, coupon_id, shop_id, goods_amount
        )
    return {
        "items": order_items,
        "goods_amount_fen": goods_amount,
        "freight_fen": freight,
        "coupon_discount_fen": coupon_discount,
        "pay_amount_fen": max(goods_amount + freight - coupon_discount, 0),
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
    coupon_id: int | None = None,
) -> Order:
    address = get_address_for_user(db, user_id, address_id)
    shop_id, order_items = _validate_order_items(db, items)
    goods_amount = sum(item["subtotal_fen"] for item in order_items)
    freight = mall_config.freight_fen
    coupon_discount = 0
    if coupon_id is not None:
        coupon_discount = _validate_user_coupon(
            db, user_id, coupon_id, shop_id, goods_amount
        )
    pay_amount = max(goods_amount + freight - coupon_discount, 0)

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
    if coupon_id is not None:
        order.coupon_id = coupon_id
        order.coupon_discount_fen = coupon_discount
        _mark_coupon_used(db, user_id, coupon_id, order.order_no)
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
    payment = PaymentDAO(db).get_active_by_order_no(order.order_no, lock=True)
    if payment is not None and payment.status == PaymentStatus.UNPAID:
        payment.is_active = False
        payment.status = PaymentStatus.FAILED
        try:
            from ..payment import get_payment_provider

            get_payment_provider().close_order(out_trade_no=payment.out_trade_no)
        except Exception as exc:
            logger.warning("关闭微信支付单失败 {}: {}", payment.out_trade_no, exc)
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
    completed_at = _utcnow()
    order.completed_at = completed_at
    if order.shipping_traces:
        traces = list(order.shipping_traces)
        traces.append(
            {"time": completed_at.isoformat(), "text": "已签收，订单完成"}
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
        "coupon_id": order.coupon_id,
        "coupon_discount_fen": order.coupon_discount_fen,
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
        "refunded_at": order.refunded_at,
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


def prepare_payment(db: Session, user_id: int, order_no: str) -> dict:
    """在短事务中创建或复用当前支付单，外部微信调用由路由在事务外完成。"""
    order = OrderDAO(db).lock_by_no(order_no)
    if order is None or order.buyer_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.status != OrderStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前订单不可支付")
    payment = PaymentDAO(db).get_active_by_order_no(order.order_no, lock=True)
    if payment is None:
        payment = PaymentDAO(db).create(
            out_trade_no=_gen_business_no("P"),
            order_no=order.order_no,
            amount_fen=order.pay_amount_fen,
            channel="wechat",
            pay_type="native",
        )
    return {
        "payment_id": payment.id,
        "out_trade_no": payment.out_trade_no,
        "order_no": order.order_no,
        "amount_fen": payment.amount_fen,
        "description": order.receiver_name,
        "code_url": payment.code_url,
        "prepay_id": payment.prepay_id,
        "expires_at": _as_utc(order.created_at)
        + timedelta(minutes=mall_config.order_pay_timeout_minutes),
    }


def save_payment_prepay(
    db: Session,
    user_id: int,
    order_no: str,
    *,
    payment_id: int,
    code_url: str | None,
    prepay_id: str | None,
) -> Payment:
    order = OrderDAO(db).lock_by_no(order_no)
    if order is None or order.buyer_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    payment = PaymentDAO(db).lock(payment_id)
    if (
        payment is None
        or payment.order_no != order.order_no
        or not payment.is_active
        or order.status != OrderStatus.PENDING_PAYMENT
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="支付单已失效")
    payment.code_url = code_url
    payment.prepay_id = prepay_id
    return payment


def _resolve_notify_url() -> str:
    from src.server.mall.payment.service import _resolve_notify_url

    return _resolve_notify_url()


def get_payment_for_buyer(db: Session, user_id: int, order_no: str) -> Payment:
    order = _get_order_for_buyer(db, user_id, order_no)
    payment = PaymentDAO(db).get_active_by_order_no(order.order_no)
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
    if not payment.is_active:
        logger.warning("忽略已关闭支付单的支付结果：{}", out_trade_no)
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
    db: Session,
    *,
    out_trade_no: str,
    transaction_id: str | None,
    amount_fen: int | None = None,
    currency: str | None = None,
    paid_at: datetime | None = None,
    require_amount: bool = False,
) -> Payment:
    """支付回调入口（微信通知 / mock 支付共用），同一短事务内完成入账。"""
    payment = PaymentDAO(db).get_by_out_trade_no(out_trade_no)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="支付记录不存在")
    if require_amount and (amount_fen is None or currency is None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付金额信息缺失")
    if amount_fen is not None and amount_fen != payment.amount_fen:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付金额不匹配")
    if currency is not None and currency != "CNY":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付币种不匹配")
    return mark_paid(
        db,
        out_trade_no=out_trade_no,
        transaction_id=transaction_id,
        paid_at=paid_at,
    )


def apply_payment_query_result(
    db: Session,
    user_id: int,
    order_no: str,
    *,
    paid: bool,
    transaction_id: str | None,
    paid_at: datetime | None,
    amount_fen: int | None,
    currency: str | None,
) -> Payment:
    payment = get_payment_for_buyer(db, user_id, order_no)
    if not paid or payment.status == PaymentStatus.SUCCESS:
        return payment
    return handle_payment_notification(
        db,
        out_trade_no=payment.out_trade_no,
        transaction_id=transaction_id,
        paid_at=paid_at,
        amount_fen=amount_fen,
        currency=currency,
        require_amount=True,
    )


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
# 退款 / 售后
# ---------------------------------------------------------------------------


def _get_shop_refund(
    db: Session, principal: AuthenticatedPrincipal, refund_no: str, *, shop_id: int | None
) -> Refund:
    shop = resolve_seller_shop(db, principal, shop_id)
    refund = RefundDAO(db).get_for_shop(refund_no, shop.id)
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款申请不存在")
    return refund


def apply_refund(
    db: Session,
    runtime: TaskRuntime,
    user_id: int,
    *,
    order_no: str,
    type: str,
    reason: str,
    description: str | None,
    evidence_images: list[str] | None,
) -> Refund:
    """买家申请退款：仅退款（未发货）或退货退款（已发货/已收货）。"""
    order = _get_order_for_buyer(db, user_id, order_no)
    if order.status not in (OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.COMPLETED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前订单状态不可申请退款")
    refund_type = RefundType(type)
    if refund_type == RefundType.REFUND_ONLY and order.status != OrderStatus.PAID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅未发货订单可申请仅退款")
    if refund_type == RefundType.RETURN_REFUND and order.status not in (
        OrderStatus.SHIPPED,
        OrderStatus.COMPLETED,
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前订单状态不支持退货退款")
    refund_dao = RefundDAO(db)
    if refund_dao.find_active_by_order(order.order_no) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该订单已有进行中的退款申请")
    refund = refund_dao.create(
        refund_no=_gen_business_no("R"),
        order_no=order.order_no,
        shop_id=order.shop_id,
        buyer_id=user_id,
        type=refund_type,
        status=RefundStatus.PENDING,
        order_status_snapshot=order.status,
        reason=reason,
        description=description,
        evidence_images=evidence_images or [],
        amount_fen=order.pay_amount_fen,
    )
    order.status = OrderStatus.REFUNDING
    OrderLogDAO(db).append(order.id, f"买家发起退款申请（{'仅退款' if refund_type == RefundType.REFUND_ONLY else '退货退款'}）：{reason}")
    runtime.enqueue(
        db,
        MALL_REFUND_AUTO_AGREE,
        refund.refund_no,
        reference=TaskReference(resource_type="mall_refund", resource_id=refund.refund_no),
        not_before=_utcnow() + timedelta(hours=mall_config.refund_auto_agree_hours),
    )
    return refund


def _restore_order_status(db: Session, order: Order, refund: Refund, message: str) -> None:
    """退款取消/驳回后把订单恢复到申请前的状态。"""
    order.status = refund.order_status_snapshot
    OrderLogDAO(db).append(order.id, message)


def cancel_refund(db: Session, user_id: int, refund_no: str) -> Refund:
    """买家取消退款申请（仅待处理状态）。"""
    refund = RefundDAO(db).lock_by_no(refund_no)
    if refund is None or refund.buyer_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款申请不存在")
    if refund.status != RefundStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可取消")
    order = OrderDAO(db).lock_by_no(refund.order_no)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    refund.status = RefundStatus.CANCELLED
    refund.refuse_reason = "买家取消退款申请"
    _restore_order_status(db, order, refund, "买家取消退款申请，订单状态已恢复")
    return refund


def submit_return_tracking(
    db: Session, user_id: int, refund_no: str, *, company: str, tracking_no: str
) -> Refund:
    """退货退款：买家填写退货物流单号。"""
    refund = RefundDAO(db).lock_by_no(refund_no)
    if refund is None or refund.buyer_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款申请不存在")
    if refund.status != RefundStatus.RETURNING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可填写退货物流")
    refund.return_tracking_company = company
    refund.return_tracking_no = tracking_no
    refund.return_shipped_at = _utcnow()
    order = OrderDAO(db).get_by_no(refund.order_no)
    if order is not None:
        OrderLogDAO(db).append(order.id, f"买家已寄回退货：{company} {tracking_no}")
    return refund


def _initiate_refund(db: Session, refund: Refund, handler_user_id: int | None) -> None:
    """发起退款：本地开发测试实现同步成功；微信支付等待退款结果通知。"""
    order = OrderDAO(db).lock_by_no(refund.order_no)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    refund.decided_at = _utcnow()
    refund.handler_user_id = handler_user_id
    from ..payment import get_payment_provider

    provider = get_payment_provider()
    payment = PaymentDAO(db).get_by_order_no(order.order_no)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="订单无支付记录，无法退款")
    refund.channel = provider.key
    try:
        result = provider.create_refund(
            out_refund_no=refund.refund_no,
            out_trade_no=payment.out_trade_no,
            amount_fen=refund.amount_fen,
            total_fen=order.pay_amount_fen,
            description=refund.reason,
        )
    except Exception as exc:
        logger.error("退款通道调用失败（{}）：{}", refund.refund_no, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"退款申请失败：{exc}"
        )
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message or "退款申请失败"
        )
    refund.channel_refund_id = result.refund_id
    refund.status = RefundStatus.REFUNDING
    OrderLogDAO(db).append(order.id, "退款申请已提交支付通道，等待退款到账")
    if provider.is_mock:
        _complete_refund_success(
            db, refund, channel_refund_id=result.refund_id, note="模拟通道退款成功"
        )


def _complete_refund_success(
    db: Session, refund: Refund, *, channel_refund_id: str | None = None, note: str = "退款成功"
) -> None:
    """退款成功入账：扣回店铺钱包、回补库存与销量、订单置为已退款；幂等。"""
    if refund.status == RefundStatus.SUCCESS:
        return
    if refund.status != RefundStatus.REFUNDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前退款状态不可完成")
    order = OrderDAO(db).lock_by_no(refund.order_no)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if channel_refund_id:
        refund.channel_refund_id = channel_refund_id
    refund.status = RefundStatus.SUCCESS
    refund.success_at = _utcnow()
    # 已确认收货的货款在可用余额，否则仍在冻结货款中
    wallet = WalletDAO(db).get_or_create(order.shop_id)
    if refund.order_status_snapshot == OrderStatus.COMPLETED:
        wallet.available_fen = max(wallet.available_fen - refund.amount_fen, 0)
        ledger_status = LedgerStatus.AVAILABLE
        ledger_note = "订单退款，从可用余额扣回"
    else:
        wallet.frozen_fen = max(wallet.frozen_fen - refund.amount_fen, 0)
        ledger_status = LedgerStatus.FROZEN
        ledger_note = "订单退款，冻结货款扣回"
    WalletLedgerDAO(db).create(
        shop_id=order.shop_id,
        entry_type=LedgerType.SALE,
        status=ledger_status,
        amount_fen=-refund.amount_fen,
        related_no=order.order_no,
        note=ledger_note,
    )
    items = OrderItemDAO(db).list_by_order(order.id)
    item_snapshots = [
        {"sku_id": item.sku_id, "goods_id": item.goods_id, "quantity": item.quantity}
        for item in items
    ]
    _restore_stock(db, item_snapshots)
    for item in items:
        goods = GoodsDAO(db).lock(item.goods_id)
        if goods is not None:
            goods.sales = max(goods.sales - item.quantity, 0)
    order.status = OrderStatus.REFUNDED
    order.refunded_at = _utcnow()
    OrderLogDAO(db).append(order.id, f"{note}，货款已退回买家")


def seller_agree_refund(
    db: Session, principal: AuthenticatedPrincipal, refund_no: str, *, shop_id: int | None = None
) -> Refund:
    """卖家同意退款：仅退款直接发起通道退款；退货退款进入等待买家寄回。"""
    refund = _get_shop_refund(db, principal, refund_no, shop_id=shop_id)
    if refund.status != RefundStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="退款申请已处理")
    if refund.type == RefundType.RETURN_REFUND:
        refund.decided_at = _utcnow()
        refund.handler_user_id = principal.user_id
        refund.status = RefundStatus.RETURNING
        order = OrderDAO(db).get_by_no(refund.order_no)
        if order is not None:
            OrderLogDAO(db).append(order.id, "卖家同意退货，等待买家寄回")
        return refund
    _initiate_refund(db, refund, principal.user_id)
    return refund


def seller_reject_refund(
    db: Session,
    principal: AuthenticatedPrincipal,
    refund_no: str,
    *,
    reason: str,
    shop_id: int | None = None,
) -> Refund:
    refund = _get_shop_refund(db, principal, refund_no, shop_id=shop_id)
    if refund.status != RefundStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="退款申请已处理")
    refund.status = RefundStatus.REJECTED
    refund.refuse_reason = reason or "卖家拒绝退款"
    refund.decided_at = _utcnow()
    refund.handler_user_id = principal.user_id
    order = OrderDAO(db).lock_by_no(refund.order_no)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    _restore_order_status(db, order, refund, f"卖家拒绝退款：{refund.refuse_reason}")
    return refund


def seller_confirm_return(
    db: Session, principal: AuthenticatedPrincipal, refund_no: str, *, shop_id: int | None = None
) -> Refund:
    """卖家确认收到退货后发起退款。"""
    refund = _get_shop_refund(db, principal, refund_no, shop_id=shop_id)
    if refund.status != RefundStatus.RETURNING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可确认收货")
    if not refund.return_tracking_no:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="买家尚未填写退货物流")
    refund.return_received_at = _utcnow()
    _initiate_refund(db, refund, principal.user_id)
    return refund


def auto_agree_refund(db: Session, refund_no: str) -> None:
    """退款超时自动同意任务调用；幂等，仅处理超时的待处理退款。"""
    refund = RefundDAO(db).lock_by_no(refund_no)
    if refund is None or refund.status != RefundStatus.PENDING:
        return
    deadline = refund.created_at + timedelta(hours=mall_config.refund_auto_agree_hours)
    if _utcnow() < _as_utc(deadline):
        return
    _agree_refund(db, refund, None)


def _agree_refund(db: Session, refund: Refund, handler_user_id: int | None) -> None:
    """同意退款的公共入口（卖家/管理员/超时任务共用）。"""
    if refund.status != RefundStatus.PENDING:
        return
    if refund.type == RefundType.RETURN_REFUND:
        refund.decided_at = _utcnow()
        refund.handler_user_id = handler_user_id
        refund.status = RefundStatus.RETURNING
        order = OrderDAO(db).get_by_no(refund.order_no)
        if order is not None:
            OrderLogDAO(db).append(order.id, "卖家同意退货，等待买家寄回")
        return
    _initiate_refund(db, refund, handler_user_id)


def handle_refund_notification(
    db: Session, *, out_refund_no: str, refund_status: str, channel_refund_id: str | None = None
) -> Refund:
    """微信退款回调入口；退款成功幂等入账。"""
    refund = RefundDAO(db).lock_by_no(out_refund_no)
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款单不存在")
    if refund_status == "SUCCESS":
        _complete_refund_success(
            db, refund, channel_refund_id=channel_refund_id, note="微信退款成功"
        )
    return refund


def refund_detail_payload(db: Session, refund: Refund) -> dict:
    order = OrderDAO(db).get_by_no(refund.order_no)
    shop = ShopDAO(db).get(refund.shop_id)
    return {
        "id": refund.id,
        "refund_no": refund.refund_no,
        "order_no": refund.order_no,
        "shop_id": refund.shop_id,
        "shop_name": shop.name if shop else None,
        "buyer_id": refund.buyer_id,
        "type": refund.type,
        "status": refund.status,
        "order_status_snapshot": refund.order_status_snapshot,
        "reason": refund.reason,
        "description": refund.description,
        "evidence_images": refund.evidence_images,
        "amount_fen": refund.amount_fen,
        "return_tracking_company": refund.return_tracking_company,
        "return_tracking_no": refund.return_tracking_no,
        "return_shipped_at": refund.return_shipped_at,
        "return_received_at": refund.return_received_at,
        "channel": refund.channel,
        "channel_refund_id": refund.channel_refund_id,
        "refuse_reason": refund.refuse_reason,
        "decided_at": refund.decided_at,
        "success_at": refund.success_at,
        "created_at": refund.created_at,
        "order": order_detail_payload(db, order) if order is not None else None,
    }


def refund_list_payloads(db: Session, refunds: list[Refund]) -> list[dict]:
    return [refund_detail_payload(db, refund) for refund in refunds]


def list_my_refunds(
    db: Session, user_id: int, page: int, page_size: int
) -> tuple[list[Refund], int]:
    return RefundDAO(db).list_for_buyer(user_id, page, page_size)


def get_my_refund(db: Session, user_id: int, refund_no: str) -> Refund:
    refund = RefundDAO(db).get_for_buyer(refund_no, user_id)
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款申请不存在")
    return refund


def seller_list_refunds(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    status_filter: RefundStatus | None,
    page: int,
    page_size: int,
    shop_id: int | None = None,
) -> tuple[list[Refund], int]:
    shop = resolve_seller_shop(db, principal, shop_id)
    return RefundDAO(db).list_for_shop(shop.id, status_filter, page, page_size)


def seller_get_refund(
    db: Session, principal: AuthenticatedPrincipal, refund_no: str, *, shop_id: int | None = None
) -> Refund:
    return _get_shop_refund(db, principal, refund_no, shop_id=shop_id)


def admin_list_refunds(
    db: Session, *, status_filter: RefundStatus | None, page: int, page_size: int
) -> tuple[list[Refund], int]:
    return RefundDAO(db).list_all(status_filter, page, page_size)


def admin_handle_refund(
    db: Session,
    refund_id: int,
    *,
    approved: bool,
    reject_reason: str | None,
    handler_user_id: int,
) -> Refund:
    """管理员仲裁退款：待处理可同意/驳回；退货中可确认并发起退款。"""
    refund = RefundDAO(db).lock(refund_id)
    if refund is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="退款申请不存在")
    if refund.status == RefundStatus.PENDING:
        if approved:
            _agree_refund(db, refund, handler_user_id)
        else:
            refund.status = RefundStatus.REJECTED
            refund.refuse_reason = reject_reason or "平台驳回退款申请"
            refund.decided_at = _utcnow()
            refund.handler_user_id = handler_user_id
            order = OrderDAO(db).lock_by_no(refund.order_no)
            if order is not None:
                _restore_order_status(db, order, refund, "平台驳回退款申请，订单状态已恢复")
        return refund
    if refund.status == RefundStatus.RETURNING and approved:
        _initiate_refund(db, refund, handler_user_id)
        return refund
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可处理")


# ---------------------------------------------------------------------------
# 商品评价 / 晒单
# ---------------------------------------------------------------------------


def create_evaluation(
    db: Session,
    user_id: int,
    *,
    order_no: str,
    order_item_id: int,
    rating: int,
    content: str,
    images: list[str] | None,
) -> Evaluation:
    """买家对已完成订单的商品发表评价（一个订单项仅可评价一次）。"""
    order = _get_order_for_buyer(db, user_id, order_no)
    if order.status != OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅确认收货后的订单可评价"
        )
    item = OrderItemDAO(db).get(order.id, order_item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="订单商品不存在"
        )
    eval_dao = EvaluationDAO(db)
    if eval_dao.get_by_order_item(order.id, order_item_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该商品已评价过"
        )
    evaluation = eval_dao.create(
        order_id=order.id,
        order_item_id=item.id,
        goods_id=item.goods_id,
        shop_id=order.shop_id,
        buyer_id=user_id,
        rating=rating,
        content=content,
        images=images or [],
    )
    OrderLogDAO(db).append(order.id, f"买家对商品「{item.goods_name}」发表了评价")
    return evaluation


def append_evaluation(
    db: Session,
    user_id: int,
    evaluation_id: int,
    *,
    content: str,
    images: list[str] | None,
) -> Evaluation:
    """买家追评（每次评价仅可追评一次）。"""
    evaluation = EvaluationDAO(db).get_for_buyer(evaluation_id, user_id)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="评价不存在"
        )
    if evaluation.appended_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该评价已追评过"
        )
    evaluation.append_content = content
    evaluation.append_images = images or []
    evaluation.appended_at = _utcnow()
    return evaluation


def seller_reply_evaluation(
    db: Session,
    principal: AuthenticatedPrincipal,
    evaluation_id: int,
    *,
    content: str,
    shop_id: int | None = None,
) -> Evaluation:
    """卖家回复本店商品评价（可多次回复，覆盖更新）。"""
    shop = resolve_seller_shop(db, principal, shop_id)
    evaluation = EvaluationDAO(db).get_for_shop(evaluation_id, shop.id)
    if evaluation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="评价不存在"
        )
    evaluation.seller_reply = content
    evaluation.seller_replied_at = _utcnow()
    return evaluation


def list_goods_evaluations(
    db: Session, goods_id: int, page: int, page_size: int
) -> tuple[list[Evaluation], dict]:
    """商品评价列表（公开）+ 评分汇总。"""
    dao = EvaluationDAO(db)
    items, total = dao.list_by_goods(goods_id, page, page_size)
    summary = dao.rating_summary(goods_id)
    summary["total"] = total
    return items, summary


def list_my_evaluations(
    db: Session, user_id: int, page: int, page_size: int
) -> tuple[list[Evaluation], int]:
    return EvaluationDAO(db).list_by_buyer(user_id, page, page_size)


def list_pending_evaluations(db: Session, user_id: int) -> list[dict]:
    """待评价列表：已完成订单中尚未评价的商品。"""
    orders = OrderDAO(db).list_completed_for_buyer(user_id)
    result: list[dict] = []
    for order in orders:
        items = OrderItemDAO(db).list_by_order(order.id)
        evaluated_ids = {
            e.order_item_id for e in EvaluationDAO(db).list_by_order(order.id)
        }
        shop = ShopDAO(db).get(order.shop_id)
        for item in items:
            if item.id in evaluated_ids:
                continue
            result.append(
                {
                    "order_no": order.order_no,
                    "order_item_id": item.id,
                    "goods_id": item.goods_id,
                    "goods_name": item.goods_name,
                    "goods_image": item.goods_image,
                    "sku_specs": item.sku_specs,
                    "shop_id": order.shop_id,
                    "shop_name": shop.name if shop else "",
                }
            )
    return result


def seller_list_evaluations(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    page: int,
    page_size: int,
    shop_id: int | None = None,
) -> tuple[list[Evaluation], int]:
    shop = resolve_seller_shop(db, principal, shop_id)
    return EvaluationDAO(db).list_for_shop(shop.id, page, page_size)


def evaluation_payload(db: Session, evaluation: Evaluation) -> dict:
    from src.server.auth.dao import UserDAO

    item = OrderItemDAO(db).get(evaluation.order_id, evaluation.order_item_id)
    order = OrderDAO(db).get(evaluation.order_id)
    buyer = UserDAO(db).get_by_id(evaluation.buyer_id)
    return {
        "id": evaluation.id,
        "order_id": evaluation.order_id,
        "order_no": order.order_no if order is not None else None,
        "order_item_id": evaluation.order_item_id,
        "goods_id": evaluation.goods_id,
        "goods_name": item.goods_name if item is not None else None,
        "goods_image": item.goods_image if item is not None else None,
        "sku_specs": item.sku_specs if item is not None else {},
        "shop_id": evaluation.shop_id,
        "buyer_id": evaluation.buyer_id,
        "buyer_username": buyer.username if buyer is not None else None,
        "rating": evaluation.rating,
        "content": evaluation.content,
        "images": evaluation.images,
        "seller_reply": evaluation.seller_reply,
        "seller_replied_at": evaluation.seller_replied_at,
        "append_content": evaluation.append_content,
        "append_images": evaluation.append_images,
        "appended_at": evaluation.appended_at,
        "created_at": evaluation.created_at,
    }


def evaluation_list_payloads(db: Session, evaluations: list[Evaluation]) -> list[dict]:
    return [evaluation_payload(db, evaluation) for evaluation in evaluations]


# ---------------------------------------------------------------------------
# 收藏/关注 + 浏览足迹
# ---------------------------------------------------------------------------


def _check_favorite_target(db: Session, target_type: FavoriteTargetType, target_id: int) -> None:
    """校验收藏目标存在：商品须为在售，店铺须为已审核通过。"""
    if target_type == FavoriteTargetType.GOODS:
        goods = GoodsDAO(db).get(target_id)
        if goods is None or goods.status != GoodsStatus.ON:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
            )
    else:
        shop = ShopDAO(db).get(target_id)
        if shop is None or shop.status != ShopStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在或未通过审核"
            )


def add_favorite(
    db: Session,
    user_id: int,
    *,
    target_type: FavoriteTargetType,
    target_id: int,
) -> Favorite:
    """收藏商品/关注店铺（幂等：已收藏直接返回）。"""
    _check_favorite_target(db, target_type, target_id)
    dao = FavoriteDAO(db)
    existing = dao.get(user_id, target_type, target_id)
    if existing is not None:
        return existing
    return dao.create(user_id=user_id, target_type=target_type, target_id=target_id)


def remove_favorite(
    db: Session,
    user_id: int,
    *,
    target_type: FavoriteTargetType,
    target_id: int,
) -> None:
    """取消收藏/关注（幂等：不存在不报错）。"""
    FavoriteDAO(db).delete(user_id, target_type, target_id)


def is_favorited(db: Session, user_id: int, *, target_type: FavoriteTargetType, target_id: int) -> bool:
    return FavoriteDAO(db).get(user_id, target_type, target_id) is not None


def favorite_payload(db: Session, favorite: Favorite) -> dict:
    """收藏记录 + 目标快照。"""
    if favorite.target_type == FavoriteTargetType.GOODS:
        goods = GoodsDAO(db).get(favorite.target_id)
        if goods is None:
            return {
                "id": favorite.id,
                "target_type": favorite.target_type.value,
                "target_id": favorite.target_id,
                "target_name": None,
                "target_image": None,
                "target_price_fen": None,
                "shop_id": None,
                "created_at": favorite.created_at,
            }
        return {
            "id": favorite.id,
            "target_type": favorite.target_type.value,
            "target_id": favorite.target_id,
            "target_name": goods.name,
            "target_image": goods.main_image,
            "target_price_fen": goods.price_fen,
            "shop_id": goods.shop_id,
            "created_at": favorite.created_at,
        }
    shop = ShopDAO(db).get(favorite.target_id)
    if shop is None:
        return {
            "id": favorite.id,
            "target_type": favorite.target_type.value,
            "target_id": favorite.target_id,
            "target_name": None,
            "target_image": None,
            "target_price_fen": None,
            "shop_id": None,
            "created_at": favorite.created_at,
        }
    return {
        "id": favorite.id,
        "target_type": favorite.target_type.value,
        "target_id": favorite.target_id,
        "target_name": shop.name,
        "target_image": shop.avatar,
        "target_price_fen": None,
        "shop_id": shop.id,
        "created_at": favorite.created_at,
    }


def list_my_favorites(
    db: Session,
    user_id: int,
    *,
    target_type: FavoriteTargetType | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    favorites, total = FavoriteDAO(db).list_for_user(user_id, target_type, page, page_size)
    return [favorite_payload(db, f) for f in favorites], total


def record_footprint(db: Session, user_id: int, *, goods_id: int) -> None:
    """记录浏览足迹（upsert：每用户每商品保留最新一条）。"""
    goods = GoodsDAO(db).get(goods_id)
    if goods is None or goods.status != GoodsStatus.ON:
        return
    FootprintDAO(db).upsert(user_id=user_id, goods_id=goods.id, shop_id=goods.shop_id)


def footprint_payload(db: Session, footprint: Footprint) -> dict:
    goods = GoodsDAO(db).get(footprint.goods_id)
    shop = ShopDAO(db).get(footprint.shop_id)
    return {
        "goods_id": footprint.goods_id,
        "goods_name": goods.name if goods is not None else None,
        "goods_image": goods.main_image if goods is not None else None,
        "price_fen": goods.price_fen if goods is not None else None,
        "shop_id": footprint.shop_id,
        "shop_name": shop.name if shop is not None else None,
        "viewed_at": footprint.viewed_at,
    }


def list_my_footprints(
    db: Session, user_id: int, page: int, page_size: int
) -> tuple[list[dict], int]:
    footprints, total = FootprintDAO(db).list_for_user(user_id, page, page_size)
    return [footprint_payload(db, f) for f in footprints], total


# ---------------------------------------------------------------------------
# 优惠券
# ---------------------------------------------------------------------------


def _coupon_discount_fen(coupon: CouponTemplate, goods_amount: int) -> int:
    """按模板计算可抵扣金额（不超过商品金额）。"""
    if coupon.type == CouponType.FIXED:
        return min(coupon.value_fen, goods_amount)
    discount = max(min(coupon.discount, 99), 1)
    return round(goods_amount * (100 - discount) / 100)


def _validate_user_coupon(
    db: Session, user_id: int, coupon_id: int, shop_id: int, goods_amount: int
) -> int:
    """校验用户券可用性（锁行）并返回可抵扣金额。"""
    user_coupon = UserCouponDAO(db).lock_for_user(user_id, coupon_id)
    if user_coupon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="优惠券不存在"
        )
    if user_coupon.status != UserCouponStatus.UNUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券不可用"
        )
    if user_coupon.expired_at is not None and _utcnow() > _as_utc(
        user_coupon.expired_at
    ):
        user_coupon.status = UserCouponStatus.EXPIRED
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券已过期"
        )
    coupon = CouponTemplateDAO(db).get(user_coupon.coupon_id)
    if coupon is None or coupon.status != CouponStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券已失效"
        )
    now = _utcnow()
    if now < _as_utc(coupon.valid_from) or now > _as_utc(coupon.valid_until):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券不在有效期内"
        )
    if goods_amount < coupon.min_amount_fen:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未满足使用门槛（满 {coupon.min_amount_fen} 分可用）",
        )
    if coupon.scope == CouponScope.SHOP and coupon.shop_id != shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该优惠券不适用于本店商品"
        )
    return _coupon_discount_fen(coupon, goods_amount)


def _mark_coupon_used(db: Session, user_id: int, coupon_id: int, order_no: str) -> None:
    """下单时把用户券置为已使用（与创建订单同一短事务）。"""
    user_coupon = UserCouponDAO(db).lock_for_user(user_id, coupon_id)
    if user_coupon is None or user_coupon.status != UserCouponStatus.UNUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券不可用"
        )
    user_coupon.status = UserCouponStatus.USED
    user_coupon.order_no = order_no
    user_coupon.used_at = _utcnow()


def list_available_coupons(
    db: Session,
    *,
    scope: CouponScope | None,
    shop_id: int | None,
    page: int,
    page_size: int,
) -> tuple[list[CouponTemplate], int]:
    """领券中心：进行中的有效券。"""
    return CouponTemplateDAO(db).list_available(
        scope=scope, shop_id=shop_id, page=page, page_size=page_size
    )


def receive_coupon(db: Session, user_id: int, coupon_id: int) -> UserCoupon:
    """领取优惠券：锁模板行防超发，校验限领次数。"""
    coupon = CouponTemplateDAO(db).lock(coupon_id)
    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="优惠券不存在"
        )
    if coupon.status != CouponStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券已失效"
        )
    now = _utcnow()
    if now < _as_utc(coupon.valid_from) or now > _as_utc(coupon.valid_until):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券不在领取时间内"
        )
    if coupon.total_count > 0 and coupon.received_count >= coupon.total_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="优惠券已被领完"
        )
    dao = UserCouponDAO(db)
    if dao.count_for_user(user_id, coupon.id) >= coupon.per_user_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="已达到每人限领数量"
        )
    coupon.received_count += 1
    return dao.create(
        user_id=user_id, coupon_id=coupon.id, expired_at=coupon.valid_until
    )


def list_my_coupons(
    db: Session,
    user_id: int,
    *,
    status_filter: UserCouponStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[UserCoupon], int]:
    """我的优惠券：查询前惰性把已过期未使用的券置为过期。"""
    UserCouponDAO(db).mark_expired()
    return UserCouponDAO(db).list_for_user(user_id, status_filter, page, page_size)


def coupon_payload(db: Session, coupon: CouponTemplate) -> dict:
    shop = ShopDAO(db).get(coupon.shop_id) if coupon.shop_id is not None else None
    return {
        "id": coupon.id,
        "name": coupon.name,
        "type": coupon.type,
        "value_fen": coupon.value_fen,
        "discount": coupon.discount,
        "min_amount_fen": coupon.min_amount_fen,
        "scope": coupon.scope,
        "shop_id": coupon.shop_id,
        "shop_name": shop.name if shop is not None else None,
        "total_count": coupon.total_count,
        "received_count": coupon.received_count,
        "per_user_limit": coupon.per_user_limit,
        "valid_from": coupon.valid_from,
        "valid_until": coupon.valid_until,
        "status": coupon.status,
        "created_at": coupon.created_at,
    }


def user_coupon_payload(db: Session, user_coupon: UserCoupon) -> dict:
    coupon = CouponTemplateDAO(db).get(user_coupon.coupon_id)
    if coupon is not None:
        shop = ShopDAO(db).get(coupon.shop_id) if coupon.shop_id is not None else None
        template = {
            "name": coupon.name,
            "type": coupon.type,
            "value_fen": coupon.value_fen,
            "discount": coupon.discount,
            "min_amount_fen": coupon.min_amount_fen,
            "scope": coupon.scope,
            "shop_id": coupon.shop_id,
            "shop_name": shop.name if shop is not None else None,
            "valid_until": coupon.valid_until,
        }
    else:
        template = {}
    return {
        "id": user_coupon.id,
        "user_id": user_coupon.user_id,
        "coupon_id": user_coupon.coupon_id,
        "status": user_coupon.status,
        "order_no": user_coupon.order_no,
        "received_at": user_coupon.received_at,
        "used_at": user_coupon.used_at,
        "expired_at": user_coupon.expired_at,
        **template,
    }


def _validate_coupon_fields(payload: dict) -> None:
    """校验券类型相关字段（创建/更新共用）。"""
    if payload.get("valid_from") is not None and payload.get("valid_until") is not None:
        if payload["valid_from"] >= payload["valid_until"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="有效期起始时间必须早于结束时间"
            )
    if payload.get("type") == CouponType.FIXED.value and payload.get("value_fen", 0) <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="满减券面额必须大于 0"
        )
    if payload.get("type") == CouponType.DISCOUNT.value:
        discount = payload.get("discount", 100)
        if not (1 <= discount <= 99):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="折扣必须在 1-99 之间"
            )
    if payload.get("total_count", 0) < 0 or payload.get("per_user_limit", 1) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="发行量/限领数量不合法"
        )


def seller_create_coupon(
    db: Session, principal: AuthenticatedPrincipal, payload: dict, *, shop_id: int | None = None
) -> CouponTemplate:
    shop = resolve_seller_shop(db, principal, shop_id)
    payload["scope"] = CouponScope.SHOP
    payload["shop_id"] = shop.id
    _validate_coupon_fields(payload)
    return CouponTemplateDAO(db).create(
        name=payload["name"],
        type=CouponType(payload["type"]),
        value_fen=payload.get("value_fen", 0),
        discount=payload.get("discount", 100),
        min_amount_fen=payload.get("min_amount_fen", 0),
        scope=CouponScope.SHOP,
        shop_id=shop.id,
        total_count=payload.get("total_count", 0),
        per_user_limit=payload.get("per_user_limit", 1),
        valid_from=payload["valid_from"],
        valid_until=payload["valid_until"],
    )


def _get_shop_coupon(
    db: Session, principal: AuthenticatedPrincipal, coupon_id: int, *, shop_id: int | None
) -> CouponTemplate:
    shop = resolve_seller_shop(db, principal, shop_id)
    coupon = CouponTemplateDAO(db).get_for_shop(coupon_id, shop.id)
    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="优惠券不存在"
        )
    return coupon


def seller_update_coupon(
    db: Session,
    principal: AuthenticatedPrincipal,
    coupon_id: int,
    payload: dict,
    *,
    shop_id: int | None = None,
) -> CouponTemplate:
    coupon = _get_shop_coupon(db, principal, coupon_id, shop_id=shop_id)
    _validate_coupon_fields(payload)
    for field in (
        "name",
        "value_fen",
        "discount",
        "min_amount_fen",
        "total_count",
        "per_user_limit",
        "valid_from",
        "valid_until",
    ):
        if field in payload:
            setattr(coupon, field, payload[field])
    return coupon


def seller_list_coupons(
    db: Session,
    principal: AuthenticatedPrincipal,
    *,
    page: int,
    page_size: int,
    shop_id: int | None = None,
) -> tuple[list[CouponTemplate], int]:
    shop = resolve_seller_shop(db, principal, shop_id)
    return CouponTemplateDAO(db).list_for_shop(shop.id, page, page_size)


def seller_set_coupon_status(
    db: Session,
    principal: AuthenticatedPrincipal,
    coupon_id: int,
    *,
    on: bool,
    shop_id: int | None = None,
) -> CouponTemplate:
    coupon = _get_shop_coupon(db, principal, coupon_id, shop_id=shop_id)
    if on:
        if coupon.status != CouponStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可上架"
            )
        coupon.status = CouponStatus.ACTIVE
    else:
        if coupon.status != CouponStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可下架"
            )
        coupon.status = CouponStatus.PAUSED
    return coupon


def admin_create_coupon(db: Session, payload: dict) -> CouponTemplate:
    scope = CouponScope(payload["scope"])
    shop_id = payload.get("shop_id")
    if scope == CouponScope.SHOP:
        if shop_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="店铺券必须指定 shop_id"
            )
        if ShopDAO(db).get(shop_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="店铺不存在"
            )
    else:
        shop_id = None
    payload["scope"] = scope
    payload["shop_id"] = shop_id
    _validate_coupon_fields(payload)
    return CouponTemplateDAO(db).create(
        name=payload["name"],
        type=CouponType(payload["type"]),
        value_fen=payload.get("value_fen", 0),
        discount=payload.get("discount", 100),
        min_amount_fen=payload.get("min_amount_fen", 0),
        scope=scope,
        shop_id=shop_id,
        total_count=payload.get("total_count", 0),
        per_user_limit=payload.get("per_user_limit", 1),
        valid_from=payload["valid_from"],
        valid_until=payload["valid_until"],
    )


def admin_update_coupon(db: Session, coupon_id: int, payload: dict) -> CouponTemplate:
    coupon = CouponTemplateDAO(db).get(coupon_id)
    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="优惠券不存在"
        )
    _validate_coupon_fields(payload)
    for field in (
        "name",
        "value_fen",
        "discount",
        "min_amount_fen",
        "total_count",
        "per_user_limit",
        "valid_from",
        "valid_until",
    ):
        if field in payload:
            setattr(coupon, field, payload[field])
    return coupon


def admin_list_coupons(
    db: Session, *, status_filter: CouponStatus | None, page: int, page_size: int
) -> tuple[list[CouponTemplate], int]:
    return CouponTemplateDAO(db).list_all(status_filter, page, page_size)


def admin_set_coupon_status(
    db: Session, coupon_id: int, *, on: bool
) -> CouponTemplate:
    coupon = CouponTemplateDAO(db).get(coupon_id)
    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="优惠券不存在"
        )
    if on:
        if coupon.status != CouponStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可上架"
            )
        coupon.status = CouponStatus.ACTIVE
    else:
        if coupon.status != CouponStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不可下架"
            )
        coupon.status = CouponStatus.PAUSED
    return coupon


def expire_coupons(db: Session) -> dict:
    """优惠券过期清理（worker 每日执行）；幂等。"""
    templates = CouponTemplateDAO(db).mark_expired_by_until()
    user_coupons = UserCouponDAO(db).mark_expired()
    return {"templates": templates, "user_coupons": user_coupons}


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
