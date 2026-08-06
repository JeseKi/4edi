# -*- coding: utf-8 -*-
"""电商商城数据模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShopStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class GoodsStatus(str, Enum):
    DRAFT = "draft"
    ON = "on"
    OFF = "off"


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WithdrawStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    SUCCESS = "success"
    FAILED = "failed"


class LedgerType(str, Enum):
    SALE = "sale"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"


class LedgerStatus(str, Enum):
    FROZEN = "frozen"
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"


class ChatSenderType(str, Enum):
    BUYER = "buyer"
    SELLER = "seller"
    SYSTEM = "system"


class Shop(Base):
    __tablename__ = "mall_shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)
    status: Mapped[ShopStatus] = mapped_column(
        SQLEnum(ShopStatus), nullable=False, default=ShopStatus.PENDING
    )
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    deposit_fen: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class Category(Base):
    __tablename__ = "mall_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("mall_categories.id", ondelete="CASCADE"), default=None
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    icon: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Goods(Base):
    __tablename__ = "mall_goods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("mall_shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("mall_categories.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    main_image: Mapped[str] = mapped_column(String(500), nullable=False)
    images: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    detail: Mapped[Optional[str]] = mapped_column(Text, default=None)
    price_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    original_price_fen: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None
    )
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[GoodsStatus] = mapped_column(
        SQLEnum(GoodsStatus), nullable=False, default=GoodsStatus.DRAFT
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (Index("ix_mall_goods_shop_status", "shop_id", "status"),)


class GoodsSku(Base):
    __tablename__ = "mall_goods_skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goods_id: Mapped[int] = mapped_column(
        ForeignKey("mall_goods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku_code: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    specs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    price_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class CartItem(Base):
    __tablename__ = "mall_cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goods_id: Mapped[int] = mapped_column(
        ForeignKey("mall_goods.id", ondelete="CASCADE"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        ForeignKey("mall_goods_skus.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_mall_cart_user_sku", "user_id", "sku_id", unique=True),
    )


class Address(Base):
    __tablename__ = "mall_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receiver: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    province: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    district: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[str] = mapped_column(String(200), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class Order(Base):
    __tablename__ = "mall_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("mall_shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING_PAYMENT
    )
    goods_amount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    freight_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    pay_amount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(50), nullable=False)
    receiver_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    receiver_address: Mapped[str] = mapped_column(String(300), nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text, default=None)
    shipping_company: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    tracking_no: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    shipping_traces: Mapped[Optional[list]] = mapped_column(JSON, default=None)
    payment_channel: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    payment_type: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    shipped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_mall_orders_buyer_status", "buyer_id", "status"),
        Index("ix_mall_orders_shop_status", "shop_id", "status"),
    )


class OrderItem(Base):
    __tablename__ = "mall_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("mall_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goods_id: Mapped[int] = mapped_column(
        ForeignKey("mall_goods.id", ondelete="CASCADE"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        ForeignKey("mall_goods_skus.id", ondelete="CASCADE"), nullable=False
    )
    goods_name: Mapped[str] = mapped_column(String(120), nullable=False)
    goods_image: Mapped[str] = mapped_column(String(500), nullable=False)
    sku_specs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    unit_price_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subtotal_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)


class OrderLog(Base):
    __tablename__ = "mall_order_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("mall_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Wallet(Base):
    __tablename__ = "mall_wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("mall_shops.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    available_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    frozen_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    deposit_fen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class WalletLedger(Base):
    __tablename__ = "mall_wallet_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("mall_shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_type: Mapped[LedgerType] = mapped_column(
        SQLEnum(LedgerType), nullable=False
    )
    status: Mapped[LedgerStatus] = mapped_column(
        SQLEnum(LedgerStatus), nullable=False
    )
    amount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    related_no: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    note: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    available_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class WithdrawRequest(Base):
    __tablename__ = "mall_withdraw_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("mall_shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    withdraw_no: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    amount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[WithdrawStatus] = mapped_column(
        SQLEnum(WithdrawStatus), nullable=False, default=WithdrawStatus.PENDING
    )
    account_info: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    handler_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    handled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Payment(Base):
    __tablename__ = "mall_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    out_trade_no: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    order_no: Mapped[str] = mapped_column(
        ForeignKey("mall_orders.order_no", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_fen: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="wechat")
    pay_type: Mapped[Optional[str]] = mapped_column(String(20), default=None)
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.UNPAID
    )
    prepay_id: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    code_url: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class ChatMessage(Base):
    __tablename__ = "mall_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        ForeignKey("mall_shops.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_no: Mapped[Optional[str]] = mapped_column(
        String(32), default=None, index=True
    )
    sender_type: Mapped[ChatSenderType] = mapped_column(
        SQLEnum(ChatSenderType), nullable=False
    )
    sender_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
