"""favorite_tables

Revision ID: fav_0007
Revises: coupon_0006
Create Date: 2026-08-17 15:00:00.000000

收藏/关注与浏览足迹：新增 mall_favorites（收藏商品/店铺）与
mall_goods_footprints（浏览足迹，每用户每商品保留最新一条）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fav_0007"
down_revision: Union[str, Sequence[str], None] = "coupon_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "mall_favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum("GOODS", "SHOP", name="favoritetargettype"),
            nullable=False,
        ),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "target_type", "target_id", name="uq_mall_favorites_user_target"
        ),
    )
    op.create_index(op.f("ix_mall_favorites_user_id"), "mall_favorites", ["user_id"], unique=False)

    op.create_table(
        "mall_goods_footprints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("goods_id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["goods_id"], ["mall_goods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "goods_id", name="uq_mall_footprints_user_goods"),
    )
    op.create_index(
        op.f("ix_mall_goods_footprints_goods_id"),
        "mall_goods_footprints",
        ["goods_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mall_goods_footprints_shop_id"),
        "mall_goods_footprints",
        ["shop_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mall_goods_footprints_user_id"),
        "mall_goods_footprints",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mall_goods_footprints_viewed_at"),
        "mall_goods_footprints",
        ["viewed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_mall_goods_footprints_viewed_at"), table_name="mall_goods_footprints"
    )
    op.drop_index(op.f("ix_mall_goods_footprints_user_id"), table_name="mall_goods_footprints")
    op.drop_index(op.f("ix_mall_goods_footprints_shop_id"), table_name="mall_goods_footprints")
    op.drop_index(op.f("ix_mall_goods_footprints_goods_id"), table_name="mall_goods_footprints")
    op.drop_table("mall_goods_footprints")
    op.drop_index(op.f("ix_mall_favorites_user_id"), table_name="mall_favorites")
    op.drop_table("mall_favorites")
