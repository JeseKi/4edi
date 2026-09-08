"""记录商家首期开放范围确认

Revision ID: shop_scope_160
Revises: agreement_online
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "shop_scope_160"
down_revision: Union[str, Sequence[str], None] = "agreement_online"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mall_shops",
        sa.Column(
            "special_license_not_required",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        )
    )
    op.add_column(
        "mall_categories",
        sa.Column(
            "requires_special_license",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE mall_categories SET requires_special_license = true "
            "WHERE name IN ('食品生鲜', '休闲零食', '药品', '医疗器械', "
            "'医疗服务', '教育培训', '金融保险')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE mall_goods SET status = 'OFF' WHERE category_id IN ("
            "SELECT child.id FROM mall_categories AS child "
            "LEFT JOIN mall_categories AS parent ON parent.id = child.parent_id "
            "WHERE child.requires_special_license = true "
            "OR parent.requires_special_license = true)"
        )
    )


def downgrade() -> None:
    op.drop_column("mall_categories", "requires_special_license")
    op.drop_column("mall_shops", "special_license_not_required")
