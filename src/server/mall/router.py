# -*- coding: utf-8 -*-
"""商城路由：买家、商家、管理员三组路由。"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Security,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.server.auth.dependencies.admin import get_current_admin
from src.server.auth.dependencies.current_user import (
    AuthenticatedPrincipal,
    get_current_principal,
)
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.task_runtime import TaskRuntime, get_task_runtime

from . import service
from .models import GoodsStatus, OrderStatus, ShopStatus, WithdrawStatus
from .schemas import (
    AddressIn,
    AddressOut,
    CartItemAddIn,
    CartItemOut,
    CartItemUpdateIn,
    CategoryCreate,
    CategoryOut,
    ChatConversationOut,
    ChatMessageCreateIn,
    ChatMessageOut,
    GoodsCreate,
    GoodsDetailOut,
    GoodsOut,
    GoodsSkuOut,
    GoodsUpdate,
    OrderCreateIn,
    OrderOut,
    OrderPreviewOut,
    PageOut,
    PaymentOut,
    PaymentPrepayIn,
    PaymentPrepayOut,
    ShopApply,
    ShopOut,
    ShopPublicOut,
    ShopReviewIn,
    ShopUpdate,
    ShipOrderIn,
    WalletLedgerOut,
    WalletOut,
    WithdrawCreateIn,
    WithdrawHandleIn,
    WithdrawOut,
)

router = APIRouter(prefix="/api/mall", tags=["商城-买家"])
seller_router = APIRouter(prefix="/api/mall/seller", tags=["商城-商家"])
admin_router = APIRouter(prefix="/api/mall/admin", tags=["商城-管理员"])

_SCOPE = [SCOPE_PROFILE_READ]


def _require_login(
    current_user: AuthenticatedPrincipal = Security(get_current_principal, scopes=_SCOPE),
) -> AuthenticatedPrincipal:
    return current_user


def _page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> tuple[int, int]:
    return page, page_size


# ---------------------------------------------------------------------------
# 买家：分类 / 商品 / 店铺
# ---------------------------------------------------------------------------


@router.get("/categories", summary="分类列表", response_model=list[CategoryOut])
async def list_categories(
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [CategoryOut.model_validate(c) for c in service.list_categories(db)]
    )


@router.post(
    "/categories",
    summary="创建分类（管理员）",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    request: Request,
    payload: CategoryCreate,
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db):
        category = service.create_category(
            db,
            name=payload.name,
            parent_id=payload.parent_id,
            sort=payload.sort,
            icon=payload.icon,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.category.create",
            resource_type="category",
            resource_id=category.id,
            target_summary=category.name,
        )
        return CategoryOut.model_validate(category)

    return await database_executor.run(_create)


@router.get("/goods", summary="商品搜索", response_model=PageOut[GoodsOut])
async def search_goods(
    keyword: str | None = Query(default=None),
    category_id: int | None = Query(default=None),
    shop_id: int | None = Query(default=None),
    sort: Literal["default", "sales", "price_asc", "price_desc", "new"] = "default",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _search(db):
        goods_list, total = service.search_goods(
            db,
            keyword=keyword,
            category_id=category_id,
            shop_id=shop_id,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [GoodsOut.model_validate(g) for g in goods_list],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_search)


@router.get("/goods/{goods_id}", summary="商品详情", response_model=GoodsDetailOut)
async def get_goods_detail(
    goods_id: int,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db):
        goods, skus, shop = service.get_goods_detail(db, goods_id)
        data = GoodsOut.model_validate(goods).model_dump()
        data["skus"] = [GoodsSkuOut.model_validate(s) for s in skus]
        data["shop"] = ShopPublicOut.model_validate(shop)
        return data

    return await database_executor.run(_get)


@router.get("/shops/{shop_id}", summary="店铺信息", response_model=ShopPublicOut)
async def get_shop_public(
    shop_id: int,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: ShopPublicOut.model_validate(service.get_public_shop(db, shop_id))
    )


# ---------------------------------------------------------------------------
# 买家：购物车
# ---------------------------------------------------------------------------


@router.post(
    "/cart/items",
    summary="加入购物车",
    response_model=CartItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_cart_item(
    payload: CartItemAddIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _add(db):
        service.add_cart_item(
            db,
            current_user.user_id,
            goods_id=payload.goods_id,
            sku_id=payload.sku_id,
            quantity=payload.quantity,
        )
        items = [item for item in service.list_cart(db, current_user.user_id) if item["sku_id"] == payload.sku_id]
        if not items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在")
        return items[0]

    return await database_executor.run(_add)


@router.get("/cart", summary="购物车列表", response_model=list[CartItemOut])
async def list_cart(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: service.list_cart(db, current_user.user_id)
    )


@router.patch("/cart/items/{item_id}", summary="更新购物车项", response_model=CartItemOut)
async def update_cart_item(
    item_id: int,
    payload: CartItemUpdateIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _update(db):
        service.update_cart_item(
            db,
            current_user.user_id,
            item_id,
            quantity=payload.quantity,
            selected=payload.selected,
        )
        items = [item for item in service.list_cart(db, current_user.user_id) if item["id"] == item_id]
        if not items:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在")
        return items[0]

    return await database_executor.run(_update)


@router.delete("/cart/items", summary="删除购物车项")
async def delete_cart_items(
    item_ids: Annotated[list[int], Query(min_length=1)],
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _delete(db):
        deleted = service.delete_cart_items(db, current_user.user_id, item_ids)
        return {"deleted": deleted}

    return await database_executor.run(_delete)


# ---------------------------------------------------------------------------
# 买家：收货地址
# ---------------------------------------------------------------------------


@router.post(
    "/addresses",
    summary="新增收货地址",
    response_model=AddressOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_address(
    payload: AddressIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: AddressOut.model_validate(
            service.create_address(db, current_user.user_id, payload.model_dump())
        )
    )


@router.get("/addresses", summary="收货地址列表", response_model=list[AddressOut])
async def list_addresses(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [AddressOut.model_validate(a) for a in service.list_addresses(db, current_user.user_id)]
    )


@router.put("/addresses/{address_id}", summary="更新收货地址", response_model=AddressOut)
async def update_address(
    address_id: int,
    payload: AddressIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: AddressOut.model_validate(
            service.update_address(db, current_user.user_id, address_id, payload.model_dump())
        )
    )


@router.delete("/addresses/{address_id}", summary="删除收货地址")
async def delete_address(
    address_id: int,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _delete(db):
        service.delete_address(db, current_user.user_id, address_id)
        return {"deleted": True}

    return await database_executor.run(_delete)


# ---------------------------------------------------------------------------
# 买家：订单
# ---------------------------------------------------------------------------


def _order_response(db: Session, order) -> dict:
    return service.order_detail_payload(db, order)


@router.post("/orders/preview", summary="订单预览", response_model=OrderPreviewOut)
async def preview_order(
    payload: OrderCreateIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _preview(db):
        result = service.preview_order(
            db, current_user.user_id, [item.model_dump() for item in payload.items]
        )
        return {
            "items": result["items"],
            "goods_amount_fen": result["goods_amount_fen"],
            "freight_fen": result["freight_fen"],
            "pay_amount_fen": result["pay_amount_fen"],
        }

    return await database_executor.run(_preview)


@router.post(
    "/orders",
    summary="创建订单",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    payload: OrderCreateIn,
    runtime: TaskRuntime = Depends(get_task_runtime),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db):
        order = service.create_order(
            db,
            runtime,
            user_id=current_user.user_id,
            address_id=payload.address_id,
            items=[item.model_dump() for item in payload.items],
            cart_item_ids=payload.cart_item_ids,
            remark=payload.remark,
        )
        return _order_response(db, order)

    return await database_executor.run(_create)


@router.get("/orders", summary="我的订单", response_model=PageOut[OrderOut])
async def list_my_orders(
    order_status: Literal["pending_payment", "paid", "shipped", "completed", "cancelled"] | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = OrderStatus(order_status) if order_status else None
        orders, total = service.list_my_orders(db, current_user.user_id, status_filter, page, page_size)
        return {
            "items": [_order_response(db, order) for order in orders],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@router.get("/orders/{order_no}", summary="订单详情", response_model=OrderOut)
async def get_my_order(
    order_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db):
        order = service.get_my_order(db, current_user.user_id, order_no)
        return _order_response(db, order)

    return await database_executor.run(_get)


@router.post("/orders/{order_no}/cancel", summary="取消订单", response_model=OrderOut)
async def cancel_order(
    order_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _cancel(db):
        order = service.cancel_order(db, current_user.user_id, order_no)
        return _order_response(db, order)

    return await database_executor.run(_cancel)


@router.post("/orders/{order_no}/confirm", summary="确认收货", response_model=OrderOut)
async def confirm_receipt(
    order_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _confirm(db):
        order = service.confirm_receipt(db, current_user.user_id, order_no)
        return _order_response(db, order)

    return await database_executor.run(_confirm)


@router.get("/orders/{order_no}/traces", summary="物流轨迹")
async def get_order_traces(
    order_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _traces(db):
        order = service.get_my_order(db, current_user.user_id, order_no)
        return {"traces": order.shipping_traces or []}

    return await database_executor.run(_traces)


# ---------------------------------------------------------------------------
# 买家：支付
# ---------------------------------------------------------------------------


@router.post("/orders/{order_no}/payment", summary="发起支付", response_model=PaymentPrepayOut)
async def create_payment(
    order_no: str,
    payload: PaymentPrepayIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db):
        payment = service.create_payment(
            db, current_user.user_id, order_no, pay_type=payload.pay_type
        )
        from .payment import get_payment_provider

        provider = get_payment_provider()
        return {
            "id": payment.id,
            "out_trade_no": payment.out_trade_no,
            "order_no": payment.order_no,
            "amount_fen": payment.amount_fen,
            "channel": payment.channel,
            "pay_type": payment.pay_type,
            "code_url": payment.code_url,
            "prepay_id": payment.prepay_id,
            "mode": provider.implementation,
        }

    return await database_executor.run(_create)


@router.get("/orders/{order_no}/payment", summary="查询支付状态", response_model=PaymentOut)
async def get_payment_status(
    order_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db):
        payment = service.get_payment_for_buyer(db, current_user.user_id, order_no)
        return PaymentOut.model_validate(payment)

    return await database_executor.run(_get)


@router.post("/payments/{out_trade_no}/mock-pay", summary="模拟支付（仅 mock 通道）")
async def mock_pay(
    out_trade_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    from .payment import get_payment_provider

    if not get_payment_provider().is_mock:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅 mock 支付通道支持模拟支付"
        )

    def _pay(db):
        payment = service.handle_payment_notification(
            db, out_trade_no=out_trade_no, transaction_id=f"mock-{out_trade_no}"
        )
        return {
            "out_trade_no": payment.out_trade_no,
            "order_no": payment.order_no,
            "status": payment.status.value,
        }

    return await database_executor.run(_pay)


@router.post(
    "/payments/wechat/notify",
    summary="微信支付回调",
    description="微信支付结果通知；验签失败返回 400，重复通知返回 SUCCESS。",
    include_in_schema=False,
)
async def wechat_pay_notify(
    request: Request,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
) -> JSONResponse:
    from .payment import get_payment_provider

    provider = get_payment_provider()
    if provider.is_mock:
        return JSONResponse({"code": "FAIL", "message": "mock 模式不接收回调"})
    body = await request.body()
    headers = dict(request.headers)
    data = provider.verify_notification(headers, body)
    if not data:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"code": "FAIL", "message": "验签失败"})
    resource = data.get("resource") or {}
    out_trade_no = resource.get("out_trade_no")
    transaction_id = resource.get("transaction_id")
    if not out_trade_no:
        return JSONResponse({"code": "FAIL", "message": "缺少商户订单号"})
    await database_executor.run(
        lambda db: service.handle_payment_notification(
            db, out_trade_no=out_trade_no, transaction_id=transaction_id
        )
    )
    return JSONResponse({"code": "SUCCESS", "message": "成功"})


# ---------------------------------------------------------------------------
# 买家 / 商家：客服消息
# ---------------------------------------------------------------------------


@router.post("/chat/messages", summary="买家发送消息", response_model=ChatMessageOut)
async def send_buyer_message(
    payload: ChatMessageCreateIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: ChatMessageOut.model_validate(
            service.send_buyer_message(
                db,
                current_user.user_id,
                shop_id=payload.shop_id,
                order_no=payload.order_no,
                content=payload.content,
            )
        )
    )


@router.get("/chat/messages", summary="买家查看会话消息", response_model=list[ChatMessageOut])
async def list_buyer_messages(
    shop_id: int,
    order_no: str | None = Query(default=None),
    after_id: int | None = Query(default=None),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [
            ChatMessageOut.model_validate(m)
            for m in service.list_buyer_messages(
                db, current_user.user_id, shop_id=shop_id, order_no=order_no, after_id=after_id
            )
        ]
    )


@router.get("/chat/conversations", summary="买家会话列表", response_model=list[ChatConversationOut])
async def list_buyer_conversations(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: service.list_buyer_conversations(db, current_user.user_id)
    )


# ---------------------------------------------------------------------------
# 商家：店铺
# ---------------------------------------------------------------------------


@seller_router.post(
    "/shop/apply", summary="申请开店", response_model=ShopOut, status_code=status.HTTP_201_CREATED
)
async def apply_shop(
    request: Request,
    payload: ShopApply,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _apply(db):
        shop = service.apply_shop(
            db,
            current_user,
            name=payload.name,
            description=payload.description,
            avatar=payload.avatar,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.shop.apply",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_apply)


@seller_router.get("/shop", summary="我的店铺", response_model=ShopOut)
async def get_my_shop(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: ShopOut.model_validate(service.get_my_shop(db, current_user))
    )


@seller_router.put("/shop", summary="更新店铺", response_model=ShopOut)
async def update_shop(
    payload: ShopUpdate,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: ShopOut.model_validate(
            service.update_shop(
                db,
                current_user,
                name=payload.name,
                description=payload.description,
                avatar=payload.avatar,
            )
        )
    )


# ---------------------------------------------------------------------------
# 商家：商品
# ---------------------------------------------------------------------------

_SELLER_SHOP_ID = "仅管理员可通过 shop_id 操作任意店铺"


def _seller_shop_id_param(
    shop_id: int | None = Query(default=None, description=_SELLER_SHOP_ID),
) -> int | None:
    return shop_id


def _chat_shop_override(
    target_shop_id: int | None = Query(default=None, description=_SELLER_SHOP_ID),
) -> int | None:
    return target_shop_id


@seller_router.get("/goods", summary="店铺商品列表", response_model=PageOut[GoodsOut])
async def seller_list_goods(
    goods_status: Literal["draft", "on", "off"] | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = GoodsStatus(goods_status) if goods_status else None
        goods_list, total = service.list_shop_goods(
            db,
            current_user,
            status_filter=status_filter,
            keyword=keyword,
            page=page,
            page_size=page_size,
            shop_id=shop_id,
        )
        return {
            "items": [GoodsOut.model_validate(g) for g in goods_list],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@seller_router.post(
    "/goods", summary="新建商品", response_model=GoodsOut, status_code=status.HTTP_201_CREATED
)
async def seller_create_goods(
    payload: GoodsCreate,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: GoodsOut.model_validate(
            service.create_goods(db, current_user, payload.model_dump(), shop_id=shop_id)
        )
    )


@seller_router.get("/goods/{goods_id}", summary="店铺商品详情", response_model=GoodsDetailOut)
async def seller_get_goods(
    goods_id: int,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db):
        goods = service.get_shop_goods(db, current_user, goods_id, shop_id=shop_id)
        skus = service.get_goods_skus(db, goods.id)
        data = GoodsOut.model_validate(goods).model_dump()
        data["skus"] = [GoodsSkuOut.model_validate(s) for s in skus]
        data["shop"] = ShopPublicOut.model_validate(service.get_shop_record(db, goods.shop_id))
        return data

    return await database_executor.run(_get)


@seller_router.put("/goods/{goods_id}", summary="更新商品", response_model=GoodsOut)
async def seller_update_goods(
    goods_id: int,
    payload: GoodsUpdate,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _update(db):
        goods = service.update_goods(
            db, current_user, goods_id, payload.model_dump(exclude_none=True), shop_id=shop_id
        )
        return GoodsOut.model_validate(goods)

    return await database_executor.run(_update)


@seller_router.post("/goods/{goods_id}/status", summary="上下架商品", response_model=GoodsOut)
async def seller_set_goods_status(
    goods_id: int,
    on: bool = Query(...),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: GoodsOut.model_validate(
            service.set_goods_status(db, current_user, goods_id, on=on, shop_id=shop_id)
        )
    )


@seller_router.delete("/goods/{goods_id}", summary="删除商品")
async def seller_delete_goods(
    goods_id: int,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _delete(db):
        service.delete_goods(db, current_user, goods_id, shop_id=shop_id)
        return {"deleted": True}

    return await database_executor.run(_delete)


# ---------------------------------------------------------------------------
# 商家：订单 / 发货
# ---------------------------------------------------------------------------


@seller_router.get("/orders", summary="店铺订单列表", response_model=PageOut[OrderOut])
async def seller_list_orders(
    order_status: Literal["pending_payment", "paid", "shipped", "completed", "cancelled"] | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = OrderStatus(order_status) if order_status else None
        orders, total = service.list_shop_orders(
            db, current_user, status_filter=status_filter, page=page, page_size=page_size, shop_id=shop_id
        )
        return {
            "items": [_order_response(db, order) for order in orders],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@seller_router.get("/orders/{order_no}", summary="店铺订单详情", response_model=OrderOut)
async def seller_get_order(
    order_no: str,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db):
        order = service.get_shop_order(db, current_user, order_no, shop_id=shop_id)
        return _order_response(db, order)

    return await database_executor.run(_get)


@seller_router.post("/orders/{order_no}/ship", summary="发货", response_model=OrderOut)
async def seller_ship_order(
    order_no: str,
    payload: ShipOrderIn,
    runtime: TaskRuntime = Depends(get_task_runtime),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _ship(db):
        order = service.ship_order(
            db,
            runtime,
            current_user,
            order_no,
            shipping_company=payload.shipping_company,
            tracking_no=payload.tracking_no,
            shop_id=shop_id,
        )
        return _order_response(db, order)

    return await database_executor.run(_ship)


# ---------------------------------------------------------------------------
# 商家：钱包 / 提现
# ---------------------------------------------------------------------------


@seller_router.get("/wallet", summary="店铺资金", response_model=WalletOut)
async def seller_get_wallet(
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: service.wallet_out(service.get_shop_wallet(db, current_user, shop_id=shop_id))
    )


@seller_router.get("/wallet/ledger", summary="资金流水", response_model=PageOut[WalletLedgerOut])
async def seller_list_ledger(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, total = service.list_wallet_ledger(
            db, current_user, page=page, page_size=page_size, shop_id=shop_id
        )
        return {
            "items": [WalletLedgerOut.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@seller_router.post(
    "/withdrawals", summary="申请提现", response_model=WithdrawOut, status_code=status.HTTP_201_CREATED
)
async def seller_request_withdraw(
    payload: WithdrawCreateIn,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: WithdrawOut.model_validate(
            service.request_withdraw(
                db,
                current_user,
                amount_fen=payload.amount_fen,
                account_info=payload.account_info,
                shop_id=shop_id,
            )
        )
    )


@seller_router.get("/withdrawals", summary="提现记录", response_model=PageOut[WithdrawOut])
async def seller_list_withdrawals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, total = service.list_my_withdrawals(
            db, current_user, page=page, page_size=page_size, shop_id=shop_id
        )
        return {
            "items": [WithdrawOut.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


# ---------------------------------------------------------------------------
# 商家：客服消息
# ---------------------------------------------------------------------------


@seller_router.post("/chat/messages", summary="商家回复消息", response_model=ChatMessageOut)
async def seller_send_message(
    payload: ChatMessageCreateIn,
    target_shop_id: int | None = Depends(_chat_shop_override),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: ChatMessageOut.model_validate(
            service.send_seller_message(
                db,
                current_user,
                shop_id=payload.shop_id,
                order_no=payload.order_no,
                content=payload.content,
                target_shop_id=target_shop_id,
            )
        )
    )


@seller_router.get("/chat/messages", summary="商家查看会话消息", response_model=list[ChatMessageOut])
async def seller_list_messages(
    shop_id: int,
    order_no: str | None = Query(default=None),
    after_id: int | None = Query(default=None),
    target_shop_id: int | None = Depends(_chat_shop_override),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [
            ChatMessageOut.model_validate(m)
            for m in service.list_seller_messages(
                db,
                current_user,
                shop_id=shop_id,
                order_no=order_no,
                after_id=after_id,
                target_shop_id=target_shop_id,
            )
        ]
    )


@seller_router.get("/chat/conversations", summary="商家会话列表", response_model=list[ChatConversationOut])
async def seller_list_conversations(
    target_shop_id: int | None = Depends(_chat_shop_override),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: service.list_seller_conversations(db, current_user, target_shop_id=target_shop_id)
    )


# ---------------------------------------------------------------------------
# 管理员
# ---------------------------------------------------------------------------


@admin_router.get("/shops", summary="店铺列表", response_model=PageOut[ShopOut])
async def admin_list_shops(
    shop_status: Literal["pending", "approved", "rejected", "closed"] | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = ShopStatus(shop_status) if shop_status else None
        shops, total = service.admin_list_shops(
            db, status_filter=status_filter, keyword=keyword, page=page, page_size=page_size
        )
        return {
            "items": [ShopOut.model_validate(s) for s in shops],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@admin_router.post("/shops/{shop_id}/review", summary="审核店铺", response_model=ShopOut)
async def admin_review_shop(
    request: Request,
    shop_id: int,
    payload: ShopReviewIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _review(db):
        shop = service.admin_review_shop(
            db,
            shop_id,
            approved=payload.approved,
            reject_reason=payload.reject_reason,
            handler_user_id=current_admin.user_id,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.shop.review",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_review)


@admin_router.post("/shops/{shop_id}/close", summary="关闭店铺", response_model=ShopOut)
async def admin_close_shop(
    request: Request,
    shop_id: int,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _close(db):
        shop = service.admin_close_shop(db, shop_id)
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.shop.close",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_close)


@admin_router.get("/withdrawals", summary="提现申请列表", response_model=PageOut[WithdrawOut])
async def admin_list_withdrawals(
    withdraw_status: Literal["pending", "approved", "rejected", "paid"] | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = WithdrawStatus(withdraw_status) if withdraw_status else None
        items, total = service.admin_list_withdrawals(
            db, status_filter=status_filter, page=page, page_size=page_size
        )
        return {
            "items": [WithdrawOut.model_validate(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@admin_router.post("/withdrawals/{withdraw_id}/handle", summary="处理提现申请", response_model=WithdrawOut)
async def admin_handle_withdraw(
    request: Request,
    withdraw_id: int,
    payload: WithdrawHandleIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _handle(db):
        item = service.admin_handle_withdraw(
            db,
            withdraw_id,
            approved=payload.approved,
            reject_reason=payload.reject_reason,
            handler_user_id=current_admin.user_id,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.withdraw.handle",
            resource_type="withdraw_request",
            resource_id=item.id,
            target_summary=item.withdraw_no,
        )
        return WithdrawOut.model_validate(item)

    return await database_executor.run(_handle)
