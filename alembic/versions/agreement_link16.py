"""修复协议阶段店铺缺失的当前协议关联

Revision ID: agreement_link16
Revises: agreement_hash15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "agreement_link16"
down_revision: Union[str, Sequence[str], None] = "agreement_hash15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 兼容协议已生成、但历史请求未写回当前协议外键的存量店铺。
    # 仅修复已经进入协议或审核阶段且外键为空的记录，不覆盖现有选择。
    op.execute(
        sa.text(
            "UPDATE mall_shops "
            "SET current_agreement_id = ("
            "SELECT shop_agreements.id FROM shop_agreements "
            "WHERE shop_agreements.shop_id = mall_shops.id "
            "AND shop_agreements.status <> 'superseded' "
            "ORDER BY shop_agreements.created_at DESC, shop_agreements.id DESC "
            "LIMIT 1"
            ") "
            "WHERE current_agreement_id IS NULL "
            "AND onboarding_stage IN ("
            "'agreement_generated', 'merchant_signed', 'platform_signed', "
            "'agreement_archived', 'approved'"
            ") "
            "AND EXISTS ("
            "SELECT 1 FROM shop_agreements "
            "WHERE shop_agreements.shop_id = mall_shops.id "
            "AND shop_agreements.status <> 'superseded'"
            ")"
        )
    )


def downgrade() -> None:
    # 无法区分迁移修复的关联与后续业务写入的关联，降级时保留数据关系。
    pass
