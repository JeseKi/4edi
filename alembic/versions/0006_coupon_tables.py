"""coupon_tables

Revision ID: coupon_0006
Revises: eval_0005
Create Date: 2026-08-17 14:00:00.000000

优惠券系统：新增 mall_coupons（券模板）与 mall_user_coupons（用户券）；
mall_orders 增加 coupon_id / coupon_discount_fen。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "coupon_0006"
down_revision: Union[str, Sequence[str], None] = "eval_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mall_coupons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.Enum("FIXED", "DISCOUNT", name="coupontype"), nullable=False),
        sa.Column("value_fen", sa.BigInteger(), nullable=False),
        sa.Column("discount", sa.Integer(), nullable=False),
        sa.Column("min_amount_fen", sa.BigInteger(), nullable=False),
        sa.Column("scope", sa.Enum("PLATFORM", "SHOP", name="couponscope"), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("received_count", sa.Integer(), nullable=False),
        sa.Column("per_user_limit", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "PAUSED", "EXPIRED", name="couponstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mall_coupons_shop_id"), "mall_coupons", ["shop_id"], unique=False)

    op.create_table(
        "mall_user_coupons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("coupon_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("UNUSED", "USED", "EXPIRED", name="usercouponstatus"),
            nullable=False,
        ),
        sa.Column("order_no", sa.String(length=32), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["coupon_id"], ["mall_coupons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mall_user_coupons_coupon_id"), "mall_user_coupons", ["coupon_id"], unique=False
    )
    op.create_index(
        op.f("ix_mall_user_coupons_user_id"), "mall_user_coupons", ["user_id"], unique=False
    )
    op.create_index(
        "ix_mall_user_coupons_user_coupon",
        "mall_user_coupons",
        ["user_id", "coupon_id"],
        unique=True,
    )

    op.add_column(
        "mall_orders",
        sa.Column("coupon_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "mall_orders",
        sa.Column("coupon_discount_fen", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("mall_orders", "coupon_discount_fen")
    op.drop_column("mall_orders", "coupon_id")
    op.drop_index("ix_mall_user_coupons_user_coupon", table_name="mall_user_coupons")
    op.drop_index(op.f("ix_mall_user_coupons_user_id"), table_name="mall_user_coupons")
    op.drop_index(op.f("ix_mall_user_coupons_coupon_id"), table_name="mall_user_coupons")
    op.drop_table("mall_user_coupons")
    op.drop_index(op.f("ix_mall_coupons_shop_id"), table_name="mall_coupons")
    op.drop_table("mall_coupons")
