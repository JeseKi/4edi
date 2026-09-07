"""增加商家在线签约留痕字段

Revision ID: agreement_online
Revises: agreement_link16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "agreement_online"
down_revision: Union[str, Sequence[str], None] = "agreement_link16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shop_agreements") as batch_op:
        batch_op.add_column(
            sa.Column("signature_mode", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("acceptance_ip", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(
            sa.Column("acceptance_user_agent", sa.String(length=500), nullable=True)
        )

    op.execute(
        "UPDATE shop_agreements "
        "SET signature_mode = 'uploaded_document' "
        "WHERE signature_mode IS NULL"
    )

    with op.batch_alter_table("shop_agreements") as batch_op:
        batch_op.alter_column(
            "signature_mode",
            existing_type=sa.String(length=32),
            nullable=False,
        )

    # SQLite 的 batch table rebuild 会触发 mall_shops.current_agreement_id 的
    # ON DELETE SET NULL，因此在列变更完成后重新建立存量当前协议关联。
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
            ")"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("shop_agreements") as batch_op:
        batch_op.drop_column("acceptance_user_agent")
        batch_op.drop_column("acceptance_ip")
        batch_op.drop_column("signature_mode")
