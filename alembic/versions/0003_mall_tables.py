"""mall_tables

Revision ID: mall_0003
Revises: user_phone_0002
Create Date: 2026-08-06 12:00:00.000000

商城功能包数据表：店铺、分类、商品、购物车、地址、订单、钱包、提现、支付、客服消息。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "mall_0003"
down_revision: Union[str, Sequence[str], None] = "user_phone_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mall_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("icon", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["mall_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mall_shops",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("avatar", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.Enum("PENDING", "APPROVED", "REJECTED", "CLOSED", name="shopstatus"), nullable=False
        ),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("deposit_fen", sa.BigInteger(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_shops_owner_user_id"), "mall_shops", ["owner_user_id"], unique=False)
    op.create_table(
        "mall_goods",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("main_image", sa.String(length=500), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("price_fen", sa.BigInteger(), nullable=False),
        sa.Column("original_price_fen", sa.BigInteger(), nullable=True),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("sales", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "ON", "OFF", name="goodsstatus"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["mall_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_goods_shop_status", "mall_goods", ["shop_id", "status"], unique=False)
    op.create_index(op.f("ix_mall_goods_shop_id"), "mall_goods", ["shop_id"], unique=False)
    op.create_table(
        "mall_goods_skus",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("goods_id", sa.Integer(), nullable=False),
        sa.Column("sku_code", sa.String(length=64), nullable=True),
        sa.Column("specs", sa.JSON(), nullable=False),
        sa.Column("price_fen", sa.BigInteger(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["goods_id"], ["mall_goods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_goods_skus_goods_id"), "mall_goods_skus", ["goods_id"], unique=False)
    op.create_table(
        "mall_cart_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("goods_id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["goods_id"], ["mall_goods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["mall_goods_skus.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_cart_user_sku", "mall_cart_items", ["user_id", "sku_id"], unique=True)
    op.create_index(op.f("ix_mall_cart_items_user_id"), "mall_cart_items", ["user_id"], unique=False)
    op.create_table(
        "mall_addresses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("receiver", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("province", sa.String(length=50), nullable=False),
        sa.Column("city", sa.String(length=50), nullable=False),
        sa.Column("district", sa.String(length=50), nullable=False),
        sa.Column("detail", sa.String(length=200), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_addresses_user_id"), "mall_addresses", ["user_id"], unique=False)
    op.create_table(
        "mall_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING_PAYMENT", "PAID", "SHIPPED", "COMPLETED", "CANCELLED", name="orderstatus"),
            nullable=False,
        ),
        sa.Column("goods_amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("freight_fen", sa.BigInteger(), nullable=False),
        sa.Column("pay_amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("receiver_name", sa.String(length=50), nullable=False),
        sa.Column("receiver_phone", sa.String(length=20), nullable=False),
        sa.Column("receiver_address", sa.String(length=300), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("shipping_company", sa.String(length=50), nullable=True),
        sa.Column("tracking_no", sa.String(length=50), nullable=True),
        sa.Column("shipping_traces", sa.JSON(), nullable=True),
        sa.Column("payment_channel", sa.String(length=20), nullable=True),
        sa.Column("payment_type", sa.String(length=20), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mall_orders_buyer_status", "mall_orders", ["buyer_id", "status"], unique=False)
    op.create_index("ix_mall_orders_shop_status", "mall_orders", ["shop_id", "status"], unique=False)
    op.create_index(op.f("ix_mall_orders_buyer_id"), "mall_orders", ["buyer_id"], unique=False)
    op.create_index(op.f("ix_mall_orders_order_no"), "mall_orders", ["order_no"], unique=True)
    op.create_index(op.f("ix_mall_orders_shop_id"), "mall_orders", ["shop_id"], unique=False)
    op.create_table(
        "mall_order_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("goods_id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("goods_name", sa.String(length=120), nullable=False),
        sa.Column("goods_image", sa.String(length=500), nullable=False),
        sa.Column("sku_specs", sa.JSON(), nullable=False),
        sa.Column("unit_price_fen", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("subtotal_fen", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["goods_id"], ["mall_goods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["mall_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sku_id"], ["mall_goods_skus.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_order_items_order_id"), "mall_order_items", ["order_id"], unique=False)
    op.create_table(
        "mall_order_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["mall_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_order_logs_order_id"), "mall_order_logs", ["order_id"], unique=False)
    op.create_table(
        "mall_wallets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("available_fen", sa.BigInteger(), nullable=False),
        sa.Column("frozen_fen", sa.BigInteger(), nullable=False),
        sa.Column("deposit_fen", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_wallets_shop_id"), "mall_wallets", ["shop_id"], unique=True)
    op.create_table(
        "mall_wallet_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.Enum("SALE", "DEPOSIT", "WITHDRAW", name="ledgertype"), nullable=False),
        sa.Column(
            "status", sa.Enum("FROZEN", "AVAILABLE", "WITHDRAWN", name="ledgerstatus"), nullable=False
        ),
        sa.Column("amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("related_no", sa.String(length=64), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_wallet_ledger_shop_id"), "mall_wallet_ledger", ["shop_id"], unique=False)
    op.create_table(
        "mall_withdraw_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("withdraw_no", sa.String(length=32), nullable=False),
        sa.Column("amount_fen", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.Enum("PENDING", "APPROVED", "REJECTED", "PAID", name="withdrawstatus"), nullable=False
        ),
        sa.Column("account_info", sa.JSON(), nullable=False),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("handler_user_id", sa.Integer(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["handler_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_withdraw_requests_shop_id"), "mall_withdraw_requests", ["shop_id"], unique=False)
    op.create_index(op.f("ix_mall_withdraw_requests_withdraw_no"), "mall_withdraw_requests", ["withdraw_no"], unique=True)
    op.create_table(
        "mall_payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("out_trade_no", sa.String(length=64), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("pay_type", sa.String(length=20), nullable=True),
        sa.Column("status", sa.Enum("UNPAID", "SUCCESS", "FAILED", name="paymentstatus"), nullable=False),
        sa.Column("prepay_id", sa.String(length=128), nullable=True),
        sa.Column("code_url", sa.String(length=512), nullable=True),
        sa.Column("transaction_id", sa.String(length=64), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_no"], ["mall_orders.order_no"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_payments_order_no"), "mall_payments", ["order_no"], unique=False)
    op.create_index(op.f("ix_mall_payments_out_trade_no"), "mall_payments", ["out_trade_no"], unique=True)
    op.create_table(
        "mall_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=True),
        sa.Column(
            "sender_type", sa.Enum("BUYER", "SELLER", "SYSTEM", name="chatsendertype"), nullable=False
        ),
        sa.Column("sender_user_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_chat_messages_order_no"), "mall_chat_messages", ["order_no"], unique=False)
    op.create_index(op.f("ix_mall_chat_messages_shop_id"), "mall_chat_messages", ["shop_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("mall_chat_messages")
    op.drop_table("mall_payments")
    op.drop_table("mall_withdraw_requests")
    op.drop_table("mall_wallet_ledger")
    op.drop_table("mall_wallets")
    op.drop_table("mall_order_logs")
    op.drop_table("mall_order_items")
    op.drop_table("mall_orders")
    op.drop_table("mall_addresses")
    op.drop_table("mall_cart_items")
    op.drop_table("mall_goods_skus")
    op.drop_table("mall_goods")
    op.drop_table("mall_shops")
    op.drop_table("mall_categories")
