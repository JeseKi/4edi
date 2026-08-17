"""evaluation_tables

Revision ID: eval_0005
Revises: refund_0004
Create Date: 2026-08-17 13:00:00.000000

商品评价/晒单：新增 mall_goods_evaluations 表（评分/内容/晒图/卖家回复/追评）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "eval_0005"
down_revision: Union[str, Sequence[str], None] = "refund_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mall_goods_evaluations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("goods_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("images", sa.JSON(), nullable=False),
        sa.Column("seller_reply", sa.Text(), nullable=True),
        sa.Column("seller_replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("append_content", sa.Text(), nullable=True),
        sa.Column("append_images", sa.JSON(), nullable=False),
        sa.Column("appended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["goods_id"], ["mall_goods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["mall_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["order_item_id"], ["mall_order_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mall_goods_evaluations_buyer_id"),
        "mall_goods_evaluations",
        ["buyer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mall_goods_evaluations_goods_id"),
        "mall_goods_evaluations",
        ["goods_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mall_goods_evaluations_order_id"),
        "mall_goods_evaluations",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mall_goods_evaluations_order_item_id"),
        "mall_goods_evaluations",
        ["order_item_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_mall_goods_evaluations_shop_id"),
        "mall_goods_evaluations",
        ["shop_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_mall_goods_evaluations_shop_id"),
        table_name="mall_goods_evaluations",
    )
    op.drop_index(
        op.f("ix_mall_goods_evaluations_order_item_id"),
        table_name="mall_goods_evaluations",
    )
    op.drop_index(
        op.f("ix_mall_goods_evaluations_order_id"),
        table_name="mall_goods_evaluations",
    )
    op.drop_index(
        op.f("ix_mall_goods_evaluations_goods_id"),
        table_name="mall_goods_evaluations",
    )
    op.drop_index(
        op.f("ix_mall_goods_evaluations_buyer_id"),
        table_name="mall_goods_evaluations",
    )
    op.drop_table("mall_goods_evaluations")
