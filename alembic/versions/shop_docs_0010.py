"""shop application documents

Revision ID: shop_docs_0010
Revises: pay_active_0009
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "shop_docs_0010"
down_revision: Union[str, Sequence[str], None] = "pay_active_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mall_shops", sa.Column("real_name", sa.String(length=50), nullable=True))
    op.add_column("mall_shops", sa.Column("identity_number", sa.String(length=32), nullable=True))
    op.add_column("mall_shops", sa.Column("business_license_asset_id", sa.String(length=500), nullable=True))
    op.add_column("mall_shops", sa.Column("identity_front_asset_id", sa.String(length=500), nullable=True))
    op.add_column("mall_shops", sa.Column("identity_back_asset_id", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("mall_shops", "identity_back_asset_id")
    op.drop_column("mall_shops", "identity_front_asset_id")
    op.drop_column("mall_shops", "business_license_asset_id")
    op.drop_column("mall_shops", "identity_number")
    op.drop_column("mall_shops", "real_name")
