# -*- coding: utf-8 -*-
"""电商商城 Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    ChatSenderType,
    CouponScope,
    CouponStatus,
    CouponType,
    FavoriteTargetType,
    GoodsStatus,
    LedgerStatus,
    LedgerType,
    OrderStatus,
    RefundStatus,
    RefundType,
    ShopStatus,
    UserCouponStatus,
    WithdrawStatus,
)

OrderStatusLiteral = Literal["pending_payment", "paid", "shipped", "completed", "cancelled", "refunding", "refunded"]
WithdrawStatusLiteral = Literal["pending", "approved", "rejected", "paid"]
GoodsStatusLiteral = Literal["draft", "on", "off"]
RefundStatusLiteral = Literal["pending", "returning", "refunding", "success", "rejected", "cancelled"]
RefundTypeLiteral = Literal["refund_only", "return_refund"]
CouponTypeLiteral = Literal["fixed", "discount"]
CouponScopeLiteral = Literal["platform", "shop"]
CouponStatusLiteral = Literal["active", "paused", "expired"]
UserCouponStatusLiteral = Literal["unused", "used", "expired"]


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    parent_id: int | None = None
    sort: int = Field(default=0, ge=0)
    icon: str | None = Field(default=None, max_length=500)


class CategoryOut(BaseModel):
    id: int
    name: str
    parent_id: int | None
    level: int
    sort: int
    icon: str | None

    model_config = ConfigDict(from_attributes=True)


class ShopApply(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    avatar: str | None = Field(default=None, max_length=500)


class ShopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    avatar: str | None = Field(default=None, max_length=500)


class ShopOut(BaseModel):
    id: int
    owner_user_id: int
    name: str
    avatar: str | None
    description: str | None
    status: ShopStatus
    reject_reason: str | None
    deposit_fen: int
    approved_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShopPublicOut(BaseModel):
    id: int
    name: str
    avatar: str | None
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class ShopReviewIn(BaseModel):
    approved: bool
    reject_reason: str | None = Field(default=None, max_length=200)


class GoodsSkuIn(BaseModel):
    sku_code: str | None = Field(default=None, max_length=64)
    specs: dict = Field(default_factory=dict)
    price_fen: int = Field(..., ge=0)
    stock: int = Field(..., ge=0)


class GoodsCreate(BaseModel):
    category_id: int | None = None
    name: str = Field(..., min_length=1, max_length=120)
    main_image: str = Field(..., max_length=500)
    images: list[str] = Field(default_factory=list)
    detail: str | None = None
    original_price_fen: int | None = Field(default=None, ge=0)
    skus: list[GoodsSkuIn] = Field(..., min_length=1, max_length=20)


class GoodsUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    main_image: str | None = Field(default=None, max_length=500)
    images: list[str] | None = None
    detail: str | None = None
    original_price_fen: int | None = Field(default=None, ge=0)
    skus: list[GoodsSkuIn] | None = Field(default=None, min_length=1, max_length=20)


class GoodsSkuOut(BaseModel):
    id: int
    goods_id: int
    sku_code: str | None
    specs: dict
    price_fen: int
    stock: int

    model_config = ConfigDict(from_attributes=True)


class GoodsOut(BaseModel):
    id: int
    shop_id: int
    category_id: int | None
    name: str
    main_image: str
    images: list
    detail: str | None
    price_fen: int
    original_price_fen: int | None
    stock: int
    sales: int
    status: GoodsStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoodsDetailOut(GoodsOut):
    shop: ShopPublicOut
    skus: list[GoodsSkuOut]


class CartItemAddIn(BaseModel):
    goods_id: int
    sku_id: int
    quantity: int = Field(..., ge=1, le=99)


class CartItemUpdateIn(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=99)
    selected: bool | None = None


class CartItemOut(BaseModel):
    id: int
    goods_id: int
    sku_id: int
    quantity: int
    selected: bool
    shop_id: int
    shop_name: str
    goods_name: str
    goods_image: str
    sku_specs: dict
    price_fen: int
    subtotal_fen: int
    stock: int
    goods_on: bool

    model_config = ConfigDict(from_attributes=True)


class AddressIn(BaseModel):
    receiver: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=5, max_length=20)
    province: str = Field(..., min_length=1, max_length=50)
    city: str = Field(..., min_length=1, max_length=50)
    district: str = Field(..., min_length=1, max_length=50)
    detail: str = Field(..., min_length=1, max_length=200)
    is_default: bool = False


class AddressOut(BaseModel):
    id: int
    user_id: int
    receiver: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemIn(BaseModel):
    sku_id: int
    quantity: int = Field(..., ge=1, le=99)


class OrderCreateIn(BaseModel):
    address_id: int
    items: list[OrderItemIn] = Field(..., min_length=1, max_length=50)
    cart_item_ids: list[int] = Field(default_factory=list)
    remark: str | None = Field(default=None, max_length=200)
    coupon_id: int | None = None


class OrderPreviewIn(BaseModel):
    items: list[OrderItemIn] = Field(..., min_length=1, max_length=50)
    coupon_id: int | None = None


class OrderPreviewItemOut(BaseModel):
    sku_id: int
    goods_id: int
    goods_name: str
    goods_image: str
    sku_specs: dict
    unit_price_fen: int
    quantity: int
    subtotal_fen: int
    stock: int


class OrderPreviewOut(BaseModel):
    items: list[OrderPreviewItemOut]
    goods_amount_fen: int
    freight_fen: int
    coupon_discount_fen: int = 0
    pay_amount_fen: int


class OrderLogOut(BaseModel):
    id: int
    order_id: int
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderItemOut(BaseModel):
    id: int
    order_id: int
    goods_id: int
    sku_id: int
    goods_name: str
    goods_image: str
    sku_specs: dict
    unit_price_fen: int
    quantity: int
    subtotal_fen: int

    model_config = ConfigDict(from_attributes=True)


class OrderOut(BaseModel):
    id: int
    order_no: str
    buyer_id: int
    shop_id: int
    shop_name: str | None = None
    status: OrderStatus
    goods_amount_fen: int
    freight_fen: int
    coupon_id: int | None = None
    coupon_discount_fen: int = 0
    pay_amount_fen: int
    receiver_name: str
    receiver_phone: str
    receiver_address: str
    remark: str | None
    shipping_company: str | None
    tracking_no: str | None
    shipping_traces: list | None
    payment_channel: str | None
    payment_type: str | None
    paid_at: datetime | None
    shipped_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    refunded_at: datetime | None
    created_at: datetime
    items: list[OrderItemOut] = Field(default_factory=list)
    logs: list[OrderLogOut] = Field(default_factory=list)


class RefundCreateIn(BaseModel):
    order_no: str = Field(..., max_length=32)
    type: RefundTypeLiteral
    reason: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    evidence_images: list[str] = Field(default_factory=list, max_length=6)


class RefundOut(BaseModel):
    id: int
    refund_no: str
    order_no: str
    shop_id: int
    shop_name: str | None = None
    buyer_id: int
    type: RefundType
    status: RefundStatus
    order_status_snapshot: OrderStatus | None = None
    reason: str
    description: str | None
    evidence_images: list
    amount_fen: int
    return_tracking_company: str | None
    return_tracking_no: str | None
    return_shipped_at: datetime | None
    return_received_at: datetime | None
    channel: str | None
    channel_refund_id: str | None
    refuse_reason: str | None
    decided_at: datetime | None
    success_at: datetime | None
    created_at: datetime
    order: OrderOut | None = None


class RefundRejectIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)


class ReturnTrackingIn(BaseModel):
    return_tracking_company: str = Field(..., min_length=1, max_length=50)
    return_tracking_no: str = Field(..., min_length=1, max_length=50)


class RefundHandleIn(BaseModel):
    approved: bool
    reject_reason: str | None = Field(default=None, max_length=200)


class EvaluationCreateIn(BaseModel):
    order_item_id: int
    rating: int = Field(..., ge=1, le=5)
    content: str = Field(..., min_length=1, max_length=1000)
    images: list[str] = Field(default_factory=list, max_length=9)


class EvaluationAppendIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    images: list[str] = Field(default_factory=list, max_length=9)


class EvaluationReplyIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


class EvaluationOut(BaseModel):
    id: int
    order_id: int
    order_no: str | None = None
    order_item_id: int
    goods_id: int
    goods_name: str | None = None
    goods_image: str | None = None
    sku_specs: dict = Field(default_factory=dict)
    shop_id: int
    buyer_id: int
    buyer_username: str | None = None
    rating: int
    content: str
    images: list
    seller_reply: str | None
    seller_replied_at: datetime | None
    append_content: str | None
    append_images: list
    appended_at: datetime | None
    created_at: datetime


class EvaluationSummaryOut(BaseModel):
    avg_rating: float
    rating_count: int
    good_rate: float
    total: int = 0


class PendingEvaluationOut(BaseModel):
    order_no: str
    order_item_id: int
    goods_id: int
    goods_name: str
    goods_image: str
    sku_specs: dict = Field(default_factory=dict)
    shop_id: int
    shop_name: str


class GoodsEvaluationListOut(BaseModel):
    items: list[EvaluationOut]
    total: int
    page: int
    page_size: int
    summary: EvaluationSummaryOut


class FavoriteAddIn(BaseModel):
    target_type: FavoriteTargetType
    target_id: int = Field(..., gt=0)


class FavoriteOut(BaseModel):
    id: int
    target_type: FavoriteTargetType
    target_id: int
    target_name: str | None = None
    target_image: str | None = None
    target_price_fen: int | None = None
    shop_id: int | None = None
    created_at: datetime


class FavoriteStatusOut(BaseModel):
    favorited: bool


class FootprintOut(BaseModel):
    goods_id: int
    goods_name: str | None = None
    goods_image: str | None = None
    price_fen: int | None = None
    shop_id: int
    shop_name: str | None = None
    viewed_at: datetime


class CouponTemplateCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: CouponTypeLiteral
    value_fen: int = Field(default=0, ge=0)
    discount: int = Field(default=100, ge=1, le=99)
    min_amount_fen: int = Field(default=0, ge=0)
    scope: CouponScopeLiteral = "platform"
    shop_id: int | None = None
    total_count: int = Field(default=0, ge=0)
    per_user_limit: int = Field(default=1, ge=1, le=100)
    valid_from: datetime
    valid_until: datetime


class CouponTemplateUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    value_fen: int | None = Field(default=None, ge=0)
    discount: int | None = Field(default=None, ge=1, le=99)
    min_amount_fen: int | None = Field(default=None, ge=0)
    total_count: int | None = Field(default=None, ge=0)
    per_user_limit: int | None = Field(default=None, ge=1, le=100)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class CouponTemplateOut(BaseModel):
    id: int
    name: str
    type: CouponType
    value_fen: int
    discount: int
    min_amount_fen: int
    scope: CouponScope
    shop_id: int | None = None
    shop_name: str | None = None
    total_count: int
    received_count: int
    per_user_limit: int
    valid_from: datetime
    valid_until: datetime
    status: CouponStatus
    created_at: datetime


class UserCouponOut(BaseModel):
    id: int
    user_id: int
    coupon_id: int
    status: UserCouponStatus
    order_no: str | None
    received_at: datetime
    used_at: datetime | None
    expired_at: datetime | None
    name: str | None = None
    type: CouponType | None = None
    value_fen: int | None = None
    discount: int | None = None
    min_amount_fen: int | None = None
    scope: CouponScope | None = None
    shop_id: int | None = None
    shop_name: str | None = None
    valid_until: datetime | None = None


class PaymentPrepayIn(BaseModel):
    pay_type: Literal["native", "jsapi"] = "native"


class PaymentPrepayOut(BaseModel):
    id: int
    out_trade_no: str
    order_no: str
    amount_fen: int
    channel: str
    pay_type: str | None
    code_url: str | None
    prepay_id: str | None
    mode: str


class PaymentOut(BaseModel):
    id: int
    out_trade_no: str
    order_no: str
    amount_fen: int
    channel: str
    pay_type: str | None
    status: str
    transaction_id: str | None
    paid_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ShipOrderIn(BaseModel):
    shipping_company: str = Field(..., min_length=1, max_length=50)
    tracking_no: str = Field(..., min_length=1, max_length=50)


class WalletOut(BaseModel):
    shop_id: int
    available_fen: int
    frozen_fen: int
    deposit_fen: int
    total_fen: int

    model_config = ConfigDict(from_attributes=True)


class WalletLedgerOut(BaseModel):
    id: int
    shop_id: int
    entry_type: LedgerType
    status: LedgerStatus
    amount_fen: int
    related_no: str | None
    note: str | None
    available_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WithdrawCreateIn(BaseModel):
    amount_fen: int = Field(..., ge=1)
    account_info: dict = Field(default_factory=dict)


class WithdrawOut(BaseModel):
    id: int
    shop_id: int
    withdraw_no: str
    amount_fen: int
    status: WithdrawStatus
    account_info: dict
    reject_reason: str | None
    handled_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WithdrawHandleIn(BaseModel):
    approved: bool
    reject_reason: str | None = Field(default=None, max_length=200)


class ChatMessageCreateIn(BaseModel):
    shop_id: int
    order_no: str | None = Field(default=None, max_length=32)
    content: str = Field(..., min_length=1, max_length=1000)


class ChatMessageOut(BaseModel):
    id: int
    shop_id: int
    order_no: str | None
    sender_type: ChatSenderType
    sender_user_id: int | None
    content: str
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatConversationOut(BaseModel):
    shop_id: int
    shop_name: str
    order_no: str | None
    last_message: str
    last_message_at: datetime
    unread_count: int


T = TypeVar("T")


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
