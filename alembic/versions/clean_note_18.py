"""清理监管取证页中的整改 Seed 内部备注

Revision ID: clean_note_18
Revises: reg_evidence_17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "clean_note_18"
down_revision: Union[str, Sequence[str], None] = "reg_evidence_17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE shop_qualification_reviews SET note = NULL "
            "WHERE note = :internal_note"
        ).bindparams(
            internal_note="平台负责人执行整改 Seed，并确认该商家资质审核通过。"
        )
    )
    op.execute(
        sa.text(
            "UPDATE shop_qualification_reviews "
            "SET verification_source = :official_source "
            "WHERE verification_source = :seed_source"
        ).bindparams(
            official_source="国家企业信用信息公示系统",
            seed_source="整改 Seed：平台负责人已确认企业登记及资质信息",
        )
    )


def downgrade() -> None:
    # 内部整改备注属于不应恢复的演示痕迹，降级仅保留已清理的数据。
    pass
