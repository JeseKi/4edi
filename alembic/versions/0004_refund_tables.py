"""refund_tables

Revision ID: refund_0004
Revises: mall_0003
Create Date: 2026-08-17 12:00:00.000000

售后退款/退货：新增 mall_refunds 表；订单状态枚举扩展 refunding/refunded；
mall_orders 增加 refunded_at。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "refund_0004"
down_revision: Union[str, Sequence[str], None] = "mall_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORDER_STATUS_VALUES = (
    "PENDING_PAYMENT",
    "PAID",
    "SHIPPED",
    "COMPLETED",
    "CANCELLED",
    "REFUNDING",
    "REFUNDED",
)


def _extend_order_status_enum() -> None:
    """为 orderstatus 枚举追加退款状态。

    PostgreSQL 使用原生 ENUM，直接 ADD VALUE；SQLite 无原生枚举，
    通过 删索引 → 重命名列 → 重建列（带新 CHECK 约束）→ 回填数据 →
    删旧列 → 重建索引 的方式扩展。
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'REFUNDING'")
        op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'REFUNDED'")
        return
    op.drop_index("ix_mall_orders_buyer_status", table_name="mall_orders")
    op.drop_index("ix_mall_orders_shop_status", table_name="mall_orders")
    op.execute("ALTER TABLE mall_orders RENAME COLUMN status TO status_old")
    op.add_column(
        "mall_orders",
        sa.Column(
            "status",
            sa.Enum(*_ORDER_STATUS_VALUES, name="orderstatus"),
            nullable=False,
            server_default="PENDING_PAYMENT",
        ),
    )
    op.execute("UPDATE mall_orders SET status = status_old")
    op.execute("ALTER TABLE mall_orders DROP COLUMN status_old")
    op.create_index("ix_mall_orders_buyer_status", "mall_orders", ["buyer_id", "status"], unique=False)
    op.create_index("ix_mall_orders_shop_status", "mall_orders", ["shop_id", "status"], unique=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mall_refunds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("refund_no", sa.String(length=32), nullable=False),
        sa.Column("order_no", sa.String(length=32), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.Enum("REFUND_ONLY", "RETURN_REFUND", name="refundtype"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "RETURNING", "REFUNDING", "SUCCESS", "REJECTED", "CANCELLED", name="refundstatus"
            ),
            nullable=False,
        ),
        sa.Column("order_status_snapshot", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence_images", sa.JSON(), nullable=False),
        sa.Column("amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("return_tracking_company", sa.String(length=50), nullable=True),
        sa.Column("return_tracking_no", sa.String(length=50), nullable=True),
        sa.Column("return_shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=True),
        sa.Column("channel_refund_id", sa.String(length=64), nullable=True),
        sa.Column("refuse_reason", sa.Text(), nullable=True),
        sa.Column("handler_user_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["handler_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_no"], ["mall_orders.order_no"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_refunds_buyer_id"), "mall_refunds", ["buyer_id"], unique=False)
    op.create_index(op.f("ix_mall_refunds_order_no"), "mall_refunds", ["order_no"], unique=False)
    op.create_index(op.f("ix_mall_refunds_refund_no"), "mall_refunds", ["refund_no"], unique=True)
    op.create_index(op.f("ix_mall_refunds_shop_id"), "mall_refunds", ["shop_id"], unique=False)

    op.add_column(
        "mall_orders",
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    )
    _extend_order_status_enum()


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE orderstatus DROP VALUE IF EXISTS 'REFUNDING'")
        op.execute("ALTER TYPE orderstatus DROP VALUE IF EXISTS 'REFUNDED'")
    op.drop_column("mall_orders", "refunded_at")
    op.drop_index(op.f("ix_mall_refunds_shop_id"), table_name="mall_refunds")
    op.drop_index(op.f("ix_mall_refunds_refund_no"), table_name="mall_refunds")
    op.drop_index(op.f("ix_mall_refunds_order_no"), table_name="mall_refunds")
    op.drop_index(op.f("ix_mall_refunds_buyer_id"), table_name="mall_refunds")
    op.drop_table("mall_refunds")
