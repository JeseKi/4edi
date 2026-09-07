# -*- coding: utf-8 -*-
"""商城路由：买家、商家、管理员三组路由。"""

from __future__ import annotations

import asyncio
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
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from src.server.auth.dependencies.admin import get_current_admin
from src.server.auth.models import User
from src.server.auth.dependencies.current_user import (
    AuthenticatedPrincipal,
    get_current_principal,
)
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.database_executor import DatabaseExecutor, get_database_executor
from src.server.files.storage import (
    FileObjectNotFoundError,
    FileStorageError,
    LocalFileStorage,
    S3FileStorage,
    get_file_storage,
)
from src.server.task_runtime import TaskRuntime, get_task_runtime

from . import service
from .models import (
    CouponScope,
    CouponStatus,
    FavoriteTargetType,
    GoodsStatus,
    OrderStatus,
    RefundStatus,
    ShopStatus,
    UserCouponStatus,
    WithdrawStatus,
)
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
    CouponTemplateCreateIn,
    CouponTemplateOut,
    CouponTemplateUpdateIn,
    ComplianceSummaryOut,
    EvaluationAppendIn,
    EvaluationCreateIn,
    EvaluationOut,
    EvaluationReplyIn,
    FavoriteAddIn,
    FavoriteOut,
    FavoriteStatusOut,
    FootprintOut,
    GoodsCreate,
    GoodsDetailOut,
    GoodsEvaluationListOut,
    GoodsOut,
    GoodsSkuOut,
    GoodsUpdate,
    OrderCreateIn,
    OrderOut,
    OrderPreviewIn,
    OrderPreviewOut,
    PageOut,
    PaymentOut,
    PaymentPrepayIn,
    PaymentPrepayOut,
    PendingEvaluationOut,
    RefundCreateIn,
    RefundHandleIn,
    RefundOut,
    RefundRejectIn,
    ReturnTrackingIn,
    MerchantAgreementAcceptIn,
    MerchantAgreementSignIn,
    PlatformAgreementSignIn,
    ShopApply,
    ShopAgreementOut,
    ShopAdminDetailOut,
    ShopOut,
    ShopPublicOut,
    ShopReviewIn,
    ShopQualificationReviewOut,
    ShopUpdate,
    ShipOrderIn,
    UserCouponOut,
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


def _agreement_out(db: Session, agreement) -> ShopAgreementOut:
    account = None
    if agreement.merchant_signed_by_user_id is not None:
        signer = db.get(User, agreement.merchant_signed_by_user_id)
        account = signer.username if signer is not None else None
    return ShopAgreementOut.model_validate(agreement).model_copy(
        update={"merchant_signed_account": account}
    )


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


@router.get(
    "/goods/{goods_id}/evaluations",
    summary="商品评价列表与评分汇总",
    response_model=GoodsEvaluationListOut,
)
async def list_goods_evaluations(
    goods_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, summary = service.list_goods_evaluations(db, goods_id, page, page_size)
        return {
            "items": service.evaluation_list_payloads(db, items),
            "total": summary["total"],
            "page": page,
            "page_size": page_size,
            "summary": {
                "avg_rating": summary["avg_rating"],
                "rating_count": summary["rating_count"],
                "good_rate": summary["good_rate"],
                "total": summary["total"],
            },
        }

    return await database_executor.run(_list)


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
    payload: OrderPreviewIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _preview(db):
        result = service.preview_order(
            db,
            current_user.user_id,
            [item.model_dump() for item in payload.items],
            coupon_id=payload.coupon_id,
        )
        return {
            "items": result["items"],
            "goods_amount_fen": result["goods_amount_fen"],
            "freight_fen": result["freight_fen"],
            "coupon_discount_fen": result["coupon_discount_fen"],
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
            coupon_id=payload.coupon_id,
        )
        return _order_response(db, order)

    return await database_executor.run(_create)


@router.get("/orders", summary="我的订单", response_model=PageOut[OrderOut])
async def list_my_orders(
    order_status: Literal["pending_payment", "paid", "shipped", "completed", "cancelled", "refunding", "refunded"] | None = Query(default=None, alias="status"),
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
    del payload
    from .payment import get_payment_provider
    from .payment.service import _resolve_notify_url

    provider = get_payment_provider()
    if configuration_error := provider.configuration_error():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=configuration_error)

    prepared = await database_executor.run(
        lambda db: service.prepare_payment(db, current_user.user_id, order_no)
    )
    if not prepared["code_url"]:
        try:
            prepay = await asyncio.to_thread(
                provider.create_prepay,
                out_trade_no=prepared["out_trade_no"],
                amount_fen=prepared["amount_fen"],
                description=prepared["description"],
                pay_type="native",
                notify_url=_resolve_notify_url(),
                expires_at=prepared["expires_at"],
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"支付下单失败：{exc}"
            ) from exc
        saved = await database_executor.run(
            lambda db: {
                "code_url": (payment := service.save_payment_prepay(
                    db,
                    current_user.user_id,
                    order_no,
                    payment_id=prepared["payment_id"],
                    code_url=prepay.code_url,
                    prepay_id=prepay.prepay_id,
                )).code_url,
                "prepay_id": payment.prepay_id,
            }
        )
        prepared["code_url"] = saved["code_url"]
        prepared["prepay_id"] = saved["prepay_id"]

    return {
        "id": prepared["payment_id"],
        "out_trade_no": prepared["out_trade_no"],
        "order_no": prepared["order_no"],
        "amount_fen": prepared["amount_fen"],
        "channel": provider.key,
        "pay_type": "native",
        "code_url": prepared["code_url"],
        "prepay_id": prepared["prepay_id"],
        "mode": provider.implementation,
        "expires_at": prepared["expires_at"],
    }


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


@router.post(
    "/orders/{order_no}/payment/refresh",
    summary="主动刷新微信支付状态",
    response_model=PaymentOut,
)
async def refresh_payment_status(
    order_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    from .payment import get_payment_provider

    payment = await database_executor.run(
        lambda db: {
            "out_trade_no": (item := service.get_payment_for_buyer(
                db, current_user.user_id, order_no
            )).out_trade_no,
            "status": item.status.value,
            "id": item.id,
        }
    )
    provider = get_payment_provider()
    if provider.is_mock:
        return await database_executor.run(
            lambda db: PaymentOut.model_validate(
                service.get_payment_for_buyer(db, current_user.user_id, order_no)
            )
        )
    result = await asyncio.to_thread(
        provider.query_order, out_trade_no=str(payment["out_trade_no"])
    )
    raw = result.raw or {}
    amount = raw.get("amount") if isinstance(raw, dict) else None
    amount_fen = amount.get("total") if isinstance(amount, dict) else None
    currency = amount.get("currency") if isinstance(amount, dict) else None

    def _apply(db):
        updated = service.apply_payment_query_result(
            db,
            current_user.user_id,
            order_no,
            paid=result.paid,
            transaction_id=result.transaction_id,
            paid_at=result.paid_at,
            amount_fen=amount_fen if isinstance(amount_fen, int) else None,
            currency=currency if isinstance(currency, str) else None,
        )
        return PaymentOut.model_validate(updated)

    return await database_executor.run(_apply)


@router.post("/payments/{out_trade_no}/mock-pay", summary="模拟支付（仅 mock 通道）")
async def mock_pay(
    out_trade_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    from .payment import get_payment_provider

    if not get_payment_provider().is_mock:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="模拟支付仅用于本地开发与测试"
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
    if resource.get("trade_state") != "SUCCESS":
        return JSONResponse({"code": "SUCCESS", "message": "忽略非成功支付通知"})
    amount = resource.get("amount") or {}
    amount_fen = amount.get("total") if isinstance(amount, dict) else None
    currency = amount.get("currency") if isinstance(amount, dict) else None
    if not out_trade_no:
        return JSONResponse({"code": "FAIL", "message": "缺少商户订单号"})
    if not isinstance(amount_fen, int) or not isinstance(currency, str):
        return JSONResponse({"code": "FAIL", "message": "缺少支付金额信息"})
    await database_executor.run(
        lambda db: service.handle_payment_notification(
            db,
            out_trade_no=out_trade_no,
            transaction_id=transaction_id,
            amount_fen=amount_fen,
            currency=currency,
            require_amount=True,
        )
    )
    return JSONResponse({"code": "SUCCESS", "message": "成功"})


@router.post(
    "/payments/wechat/refund-notify",
    summary="微信退款回调",
    description="微信退款结果通知；验签失败返回 400，退款成功幂等入账。",
    include_in_schema=False,
)
async def wechat_refund_notify(
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
    out_refund_no = resource.get("out_refund_no")
    refund_status = resource.get("refund_status")
    channel_refund_id = resource.get("refund_id")
    if not out_refund_no:
        return JSONResponse({"code": "FAIL", "message": "缺少商户退款单号"})
    await database_executor.run(
        lambda db: service.handle_refund_notification(
            db,
            out_refund_no=out_refund_no,
            refund_status=refund_status or "",
            channel_refund_id=channel_refund_id,
        )
    )
    return JSONResponse({"code": "SUCCESS", "message": "成功"})


# ---------------------------------------------------------------------------
# 买家：退款 / 售后
# ---------------------------------------------------------------------------


def _refund_response(db: Session, refund) -> dict:
    return service.refund_detail_payload(db, refund)


@router.post(
    "/refunds",
    summary="申请退款",
    response_model=RefundOut,
    status_code=status.HTTP_201_CREATED,
)
async def apply_refund(
    payload: RefundCreateIn,
    runtime: TaskRuntime = Depends(get_task_runtime),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _apply(db):
        refund = service.apply_refund(
            db,
            runtime,
            current_user.user_id,
            order_no=payload.order_no,
            type=payload.type,
            reason=payload.reason,
            description=payload.description,
            evidence_images=payload.evidence_images,
        )
        return _refund_response(db, refund)

    return await database_executor.run(_apply)


@router.get("/refunds", summary="我的退款申请", response_model=PageOut[RefundOut])
async def list_my_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        refunds, total = service.list_my_refunds(
            db, current_user.user_id, page, page_size
        )
        return {
            "items": [_refund_response(db, refund) for refund in refunds],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@router.get("/refunds/{refund_no}", summary="退款申请详情", response_model=RefundOut)
async def get_my_refund(
    refund_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db):
        refund = service.get_my_refund(db, current_user.user_id, refund_no)
        return _refund_response(db, refund)

    return await database_executor.run(_get)


@router.post("/refunds/{refund_no}/cancel", summary="取消退款申请", response_model=RefundOut)
async def cancel_refund(
    refund_no: str,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _cancel(db):
        refund = service.cancel_refund(db, current_user.user_id, refund_no)
        return _refund_response(db, refund)

    return await database_executor.run(_cancel)


@router.post(
    "/refunds/{refund_no}/return-tracking",
    summary="填写退货物流",
    response_model=RefundOut,
)
async def submit_return_tracking(
    refund_no: str,
    payload: ReturnTrackingIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _submit(db):
        refund = service.submit_return_tracking(
            db,
            current_user.user_id,
            refund_no,
            company=payload.return_tracking_company,
            tracking_no=payload.return_tracking_no,
        )
        return _refund_response(db, refund)

    return await database_executor.run(_submit)


# ---------------------------------------------------------------------------
# 买家：商品评价 / 晒单
# ---------------------------------------------------------------------------


def _evaluation_response(db: Session, evaluation) -> dict:
    return service.evaluation_payload(db, evaluation)


@router.post(
    "/orders/{order_no}/evaluations",
    summary="发表商品评价",
    response_model=EvaluationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluation(
    order_no: str,
    payload: EvaluationCreateIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db):
        evaluation = service.create_evaluation(
            db,
            current_user.user_id,
            order_no=order_no,
            order_item_id=payload.order_item_id,
            rating=payload.rating,
            content=payload.content,
            images=payload.images,
        )
        return _evaluation_response(db, evaluation)

    return await database_executor.run(_create)


@router.get(
    "/evaluations/pending",
    summary="待评价商品列表",
    response_model=list[PendingEvaluationOut],
)
async def list_pending_evaluations(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: service.list_pending_evaluations(db, current_user.user_id)
    )


@router.get(
    "/evaluations/mine",
    summary="我的已评价列表",
    response_model=PageOut[EvaluationOut],
)
async def list_my_evaluations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, total = service.list_my_evaluations(
            db, current_user.user_id, page, page_size
        )
        return {
            "items": service.evaluation_list_payloads(db, items),
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@router.post(
    "/evaluations/{evaluation_id}/append",
    summary="追评",
    response_model=EvaluationOut,
)
async def append_evaluation(
    evaluation_id: int,
    payload: EvaluationAppendIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _append(db):
        evaluation = service.append_evaluation(
            db,
            current_user.user_id,
            evaluation_id,
            content=payload.content,
            images=payload.images,
        )
        return _evaluation_response(db, evaluation)

    return await database_executor.run(_append)


# ---------------------------------------------------------------------------
# 买家：收藏/关注 + 浏览足迹
# ---------------------------------------------------------------------------


@router.post(
    "/favorites",
    summary="收藏商品/关注店铺",
    response_model=FavoriteOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_favorite(
    payload: FavoriteAddIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _add(db):
        favorite = service.add_favorite(
            db,
            current_user.user_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
        return service.favorite_payload(db, favorite)

    return await database_executor.run(_add)


@router.delete("/favorites", summary="取消收藏/取关店铺")
async def remove_favorite(
    target_type: FavoriteTargetType,
    target_id: int = Query(..., gt=0),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _remove(db):
        service.remove_favorite(
            db,
            current_user.user_id,
            target_type=target_type,
            target_id=target_id,
        )
        return {"ok": True}

    return await database_executor.run(_remove)


@router.get("/favorites", summary="我的收藏列表", response_model=PageOut[FavoriteOut])
async def list_my_favorites(
    target_type: FavoriteTargetType | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, total = service.list_my_favorites(
            db,
            current_user.user_id,
            target_type=target_type,
            page=page,
            page_size=page_size,
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@router.get(
    "/favorites/status",
    summary="查询收藏状态",
    response_model=FavoriteStatusOut,
)
async def get_favorite_status(
    target_type: FavoriteTargetType,
    target_id: int = Query(..., gt=0),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _status(db):
        favorited = service.is_favorited(
            db, current_user.user_id, target_type=target_type, target_id=target_id
        )
        return {"favorited": favorited}

    return await database_executor.run(_status)


@router.post("/footprints", summary="记录浏览足迹")
async def record_footprint(
    goods_id: int = Query(..., gt=0),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _record(db):
        service.record_footprint(db, current_user.user_id, goods_id=goods_id)
        return {"ok": True}

    return await database_executor.run(_record)


@router.get("/footprints", summary="我的浏览足迹", response_model=PageOut[FootprintOut])
async def list_my_footprints(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, total = service.list_my_footprints(
            db, current_user.user_id, page, page_size
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


# ---------------------------------------------------------------------------
# 买家：优惠券
# ---------------------------------------------------------------------------


@router.get("/coupons", summary="领券中心", response_model=PageOut[CouponTemplateOut])
async def list_available_coupons(
    scope: Literal["platform", "shop"] | None = Query(default=None),
    shop_id: int | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        scope_filter = CouponScope(scope) if scope else None
        items, total = service.list_available_coupons(
            db, scope=scope_filter, shop_id=shop_id, page=page, page_size=page_size
        )
        return {
            "items": [service.coupon_payload(db, c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@router.post(
    "/coupons/{coupon_id}/receive",
    summary="领取优惠券",
    response_model=UserCouponOut,
    status_code=status.HTTP_201_CREATED,
)
async def receive_coupon(
    coupon_id: int,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _receive(db):
        user_coupon = service.receive_coupon(db, current_user.user_id, coupon_id)
        return service.user_coupon_payload(db, user_coupon)

    return await database_executor.run(_receive)


@router.get("/coupons/mine", summary="我的优惠券", response_model=PageOut[UserCouponOut])
async def list_my_coupons(
    coupon_status: Literal["unused", "used", "expired"] | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = UserCouponStatus(coupon_status) if coupon_status else None
        items, total = service.list_my_coupons(
            db, current_user.user_id, status_filter=status_filter, page=page, page_size=page_size
        )
        return {
            "items": [service.user_coupon_payload(db, c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


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
            payload.model_dump(),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
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


@seller_router.post(
    "/shop/qualification/resubmit",
    summary="重新提交店铺资质",
    response_model=ShopOut,
)
async def resubmit_shop_qualification(
    request: Request,
    payload: ShopApply,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _resubmit(db):
        shop = service.resubmit_shop_qualification(
            db,
            current_user,
            payload.model_dump(),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="mall.shop.qualification.resubmit",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_resubmit)


@seller_router.get("/shop", summary="我的店铺", response_model=ShopOut)
async def get_my_shop(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: ShopOut.model_validate(service.get_my_shop(db, current_user))
    )


@seller_router.get(
    "/shop/agreement",
    summary="查看当前商家入驻协议定稿",
    response_model=ShopAgreementOut,
)
async def get_my_shop_agreement(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: _agreement_out(
            db, service.get_my_shop_agreement(db, current_user)
        )
    )


@seller_router.post(
    "/shop/agreement/accept",
    summary="商家在线签署电子协议",
    response_model=ShopOut,
)
async def merchant_accept_shop_agreement(
    request: Request,
    payload: MerchantAgreementAcceptIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _accept(db):
        shop = service.merchant_accept_shop_agreement(
            db,
            current_user,
            payload.model_dump(),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="mall.shop.agreement.accept",
            resource_type="shop_agreement",
            resource_id=shop.current_agreement_id,
            target_summary=shop.current_agreement.agreement_number
            if shop.current_agreement
            else shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_accept)


@seller_router.get(
    "/shop/agreement/signed-file",
    summary="下载当前商家的双方签署协议",
)
async def download_my_shop_signed_agreement(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    snapshot = await database_executor.run(
        lambda db: service.get_my_shop_signed_agreement_snapshot(db, current_user)
    )
    storage = get_file_storage()
    if snapshot.storage_driver != storage.driver:
        raise HTTPException(status_code=409, detail="文件存储配置已变更，无法下载")
    try:
        if isinstance(storage, LocalFileStorage):
            return FileResponse(
                storage.path_for_download(snapshot.storage_key),
                media_type=snapshot.content_type,
                filename=snapshot.original_filename,
                content_disposition_type="attachment",
            )
        if isinstance(storage, S3FileStorage):
            return RedirectResponse(
                storage.download_url(snapshot.storage_key, snapshot.original_filename),
                status_code=307,
            )
    except FileObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="双方签署协议文件不存在") from exc
    raise HTTPException(status_code=500, detail="不支持的文件存储驱动")


@seller_router.post(
    "/shop/agreement/merchant-sign",
    summary="商家提交已签署协议",
    response_model=ShopOut,
)
async def merchant_sign_shop_agreement(
    request: Request,
    payload: MerchantAgreementSignIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _sign(db):
        shop = service.merchant_sign_shop_agreement(
            db,
            current_user,
            payload.model_dump(),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="mall.shop.agreement.merchant_sign",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_sign)


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
    order_status: Literal["pending_payment", "paid", "shipped", "completed", "cancelled", "refunding", "refunded"] | None = Query(default=None, alias="status"),
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
# 商家：退款 / 售后
# ---------------------------------------------------------------------------


@seller_router.get("/refunds", summary="店铺退款申请列表", response_model=PageOut[RefundOut])
async def seller_list_refunds(
    refund_status: Literal["pending", "returning", "refunding", "success", "rejected", "cancelled"] | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = RefundStatus(refund_status) if refund_status else None
        refunds, total = service.seller_list_refunds(
            db, current_user, status_filter=status_filter, page=page, page_size=page_size, shop_id=shop_id
        )
        return {
            "items": [_refund_response(db, refund) for refund in refunds],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@seller_router.get("/refunds/{refund_no}", summary="店铺退款申请详情", response_model=RefundOut)
async def seller_get_refund(
    refund_no: str,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db):
        refund = service.seller_get_refund(db, current_user, refund_no, shop_id=shop_id)
        return _refund_response(db, refund)

    return await database_executor.run(_get)


@seller_router.post("/refunds/{refund_no}/agree", summary="同意退款", response_model=RefundOut)
async def seller_agree_refund(
    refund_no: str,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _agree(db):
        refund = service.seller_agree_refund(db, current_user, refund_no, shop_id=shop_id)
        return _refund_response(db, refund)

    return await database_executor.run(_agree)


@seller_router.post("/refunds/{refund_no}/reject", summary="拒绝退款", response_model=RefundOut)
async def seller_reject_refund(
    refund_no: str,
    payload: RefundRejectIn,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _reject(db):
        refund = service.seller_reject_refund(
            db, current_user, refund_no, reason=payload.reason, shop_id=shop_id
        )
        return _refund_response(db, refund)

    return await database_executor.run(_reject)


@seller_router.post(
    "/refunds/{refund_no}/confirm-return",
    summary="确认收到退货并发起退款",
    response_model=RefundOut,
)
async def seller_confirm_return(
    refund_no: str,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _confirm(db):
        refund = service.seller_confirm_return(db, current_user, refund_no, shop_id=shop_id)
        return _refund_response(db, refund)

    return await database_executor.run(_confirm)


# ---------------------------------------------------------------------------
# 商家：商品评价
# ---------------------------------------------------------------------------


@seller_router.get(
    "/evaluations",
    summary="店铺评价列表",
    response_model=PageOut[EvaluationOut],
)
async def seller_list_evaluations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, total = service.seller_list_evaluations(
            db, current_user, page=page, page_size=page_size, shop_id=shop_id
        )
        return {
            "items": service.evaluation_list_payloads(db, items),
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@seller_router.post(
    "/evaluations/{evaluation_id}/reply",
    summary="回复评价",
    response_model=EvaluationOut,
)
async def seller_reply_evaluation(
    evaluation_id: int,
    payload: EvaluationReplyIn,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _reply(db):
        evaluation = service.seller_reply_evaluation(
            db,
            current_user,
            evaluation_id,
            content=payload.content,
            shop_id=shop_id,
        )
        return _evaluation_response(db, evaluation)

    return await database_executor.run(_reply)


# ---------------------------------------------------------------------------
# 商家：优惠券
# ---------------------------------------------------------------------------


@seller_router.get("/coupons", summary="店铺优惠券列表", response_model=PageOut[CouponTemplateOut])
async def seller_list_coupons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        items, total = service.seller_list_coupons(
            db, current_user, page=page, page_size=page_size, shop_id=shop_id
        )
        return {
            "items": [service.coupon_payload(db, c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@seller_router.post(
    "/coupons",
    summary="新建店铺优惠券",
    response_model=CouponTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def seller_create_coupon(
    payload: CouponTemplateCreateIn,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db):
        coupon = service.seller_create_coupon(
            db, current_user, payload.model_dump(), shop_id=shop_id
        )
        return service.coupon_payload(db, coupon)

    return await database_executor.run(_create)


@seller_router.put("/coupons/{coupon_id}", summary="更新店铺优惠券", response_model=CouponTemplateOut)
async def seller_update_coupon(
    coupon_id: int,
    payload: CouponTemplateUpdateIn,
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _update(db):
        coupon = service.seller_update_coupon(
            db, current_user, coupon_id, payload.model_dump(exclude_none=True), shop_id=shop_id
        )
        return service.coupon_payload(db, coupon)

    return await database_executor.run(_update)


@seller_router.post("/coupons/{coupon_id}/status", summary="上下架店铺优惠券", response_model=CouponTemplateOut)
async def seller_set_coupon_status(
    coupon_id: int,
    on: bool = Query(...),
    shop_id: int | None = Depends(_seller_shop_id_param),
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _set(db):
        coupon = service.seller_set_coupon_status(
            db, current_user, coupon_id, on=on, shop_id=shop_id
        )
        return service.coupon_payload(db, coupon)

    return await database_executor.run(_set)


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
    qualification_state: Literal["expiring_soon", "expired"] | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = ShopStatus(shop_status) if shop_status else None
        shops, total = service.admin_list_shops(
            db,
            status_filter=status_filter,
            qualification_state=qualification_state,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [ShopOut.model_validate(s) for s in shops],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@admin_router.get(
    "/compliance-summary", summary="合规待办汇总", response_model=ComplianceSummaryOut
)
async def admin_compliance_summary(
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(service.compliance_summary)


@admin_router.get(
    "/shops/{shop_id}", summary="店铺资质详情", response_model=ShopAdminDetailOut
)
async def admin_shop_detail(
    shop_id: int,
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _detail(db):
        shop, reviews = service.admin_shop_detail(db, shop_id)
        return {
            "shop": ShopOut.model_validate(shop),
            "qualification_reviews": [
                ShopQualificationReviewOut.model_validate(review) for review in reviews
            ],
        }

    return await database_executor.run(_detail)


@admin_router.get(
    "/shops/{shop_id}/agreement",
    summary="查看商家完整入驻协议",
    response_model=ShopAgreementOut,
)
async def admin_get_shop_agreement(
    shop_id: int,
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: _agreement_out(db, service.admin_get_shop_agreement(db, shop_id))
    )


@admin_router.post("/shops/{shop_id}/review", summary="店铺资质预审", response_model=ShopOut)
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
            payload=payload.model_dump(),
            handler_user_id=current_admin.user_id,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.shop.qualification.pre_review",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_review)


@admin_router.post(
    "/shops/{shop_id}/agreement/generate",
    summary="生成商家入驻协议定稿",
    response_model=ShopAgreementOut,
)
async def admin_generate_shop_agreement(
    request: Request,
    shop_id: int,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _generate(db):
        agreement = service.admin_generate_shop_agreement(
            db, shop_id, handler_user_id=current_admin.user_id
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="mall.shop.agreement.generate",
            resource_type="shop_agreement",
            resource_id=agreement.id,
            target_summary=agreement.agreement_number,
        )
        return _agreement_out(db, agreement)

    return await database_executor.run(_generate)


@admin_router.post(
    "/shops/{shop_id}/agreement/platform-sign",
    summary="平台提交双方签署协议",
    response_model=ShopOut,
)
async def admin_platform_sign_shop_agreement(
    request: Request,
    shop_id: int,
    payload: PlatformAgreementSignIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _sign(db):
        shop = service.admin_platform_sign_shop_agreement(
            db,
            shop_id,
            payload.model_dump(),
            handler_user_id=current_admin.user_id,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="mall.shop.agreement.platform_sign",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_sign)


@admin_router.post(
    "/shops/{shop_id}/agreement/archive",
    summary="归档最终商家入驻协议",
    response_model=ShopOut,
)
async def admin_archive_shop_agreement(
    request: Request,
    shop_id: int,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    snapshot = await database_executor.run(
        lambda db: service.prepare_shop_agreement_archive(db, shop_id)
    )
    storage = get_file_storage()
    if snapshot.storage_driver != storage.driver:
        raise HTTPException(status_code=409, detail="文件存储配置已变更，无法归档")
    try:
        final_file_sha256 = await asyncio.to_thread(
            storage.sha256, snapshot.storage_key
        )
    except FileObjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="最终协议文件对象不存在") from exc
    except FileStorageError as exc:
        raise HTTPException(status_code=502, detail="读取最终协议文件失败") from exc

    def _archive(db):
        shop = service.admin_archive_shop_agreement(
            db,
            shop_id,
            handler_user_id=current_admin.user_id,
            expected_asset_id=snapshot.id,
            final_file_sha256=final_file_sha256,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="mall.shop.agreement.archive",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
            detail={"final_file_sha256": final_file_sha256},
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_archive)


@admin_router.post(
    "/shops/{shop_id}/approve",
    summary="最终批准商家入驻",
    response_model=ShopOut,
)
async def admin_approve_shop(
    request: Request,
    shop_id: int,
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _approve(db):
        shop = service.admin_approve_shop(db, shop_id)
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="mall.shop.approve",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_approve)


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


@admin_router.post("/shops/{shop_id}/reopen", summary="开启店铺", response_model=ShopOut)
async def admin_reopen_shop(
    request: Request,
    shop_id: int,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _reopen(db):
        shop = service.admin_reopen_shop(db, shop_id)
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.shop.reopen",
            resource_type="shop",
            resource_id=shop.id,
            target_summary=shop.name,
        )
        return ShopOut.model_validate(shop)

    return await database_executor.run(_reopen)


@admin_router.get("/refunds", summary="退款申请列表", response_model=PageOut[RefundOut])
async def admin_list_refunds(
    refund_status: Literal["pending", "returning", "refunding", "success", "rejected", "cancelled"] | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = RefundStatus(refund_status) if refund_status else None
        refunds, total = service.admin_list_refunds(
            db, status_filter=status_filter, page=page, page_size=page_size
        )
        return {
            "items": [_refund_response(db, refund) for refund in refunds],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@admin_router.post("/refunds/{refund_id}/handle", summary="仲裁退款申请", response_model=RefundOut)
async def admin_handle_refund(
    request: Request,
    refund_id: int,
    payload: RefundHandleIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _handle(db):
        item = service.admin_handle_refund(
            db,
            refund_id,
            approved=payload.approved,
            reject_reason=payload.reject_reason,
            handler_user_id=current_admin.user_id,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.refund.handle",
            resource_type="refund",
            resource_id=item.id,
            target_summary=item.refund_no,
        )
        return _refund_response(db, item)

    return await database_executor.run(_handle)


@admin_router.get("/coupons", summary="平台优惠券列表", response_model=PageOut[CouponTemplateOut])
async def admin_list_coupons(
    coupon_status: Literal["active", "paused", "expired"] | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db):
        status_filter = CouponStatus(coupon_status) if coupon_status else None
        items, total = service.admin_list_coupons(
            db, status_filter=status_filter, page=page, page_size=page_size
        )
        return {
            "items": [service.coupon_payload(db, c) for c in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    return await database_executor.run(_list)


@admin_router.post(
    "/coupons",
    summary="创建平台/店铺优惠券",
    response_model=CouponTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_coupon(
    request: Request,
    payload: CouponTemplateCreateIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db):
        coupon = service.admin_create_coupon(db, payload.model_dump())
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.coupon.create",
            resource_type="coupon",
            resource_id=coupon.id,
            target_summary=coupon.name,
        )
        return service.coupon_payload(db, coupon)

    return await database_executor.run(_create)


@admin_router.put("/coupons/{coupon_id}", summary="更新优惠券", response_model=CouponTemplateOut)
async def admin_update_coupon(
    request: Request,
    coupon_id: int,
    payload: CouponTemplateUpdateIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _update(db):
        coupon = service.admin_update_coupon(
            db, coupon_id, payload.model_dump(exclude_none=True)
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.coupon.update",
            resource_type="coupon",
            resource_id=coupon.id,
            target_summary=coupon.name,
        )
        return service.coupon_payload(db, coupon)

    return await database_executor.run(_update)


@admin_router.post("/coupons/{coupon_id}/status", summary="上下架优惠券", response_model=CouponTemplateOut)
async def admin_set_coupon_status(
    request: Request,
    coupon_id: int,
    on: bool = Query(...),
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _set(db):
        coupon = service.admin_set_coupon_status(db, coupon_id, on=on)
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="mall.coupon.status",
            resource_type="coupon",
            resource_id=coupon.id,
            target_summary=coupon.name,
        )
        return service.coupon_payload(db, coupon)

    return await database_executor.run(_set)


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
