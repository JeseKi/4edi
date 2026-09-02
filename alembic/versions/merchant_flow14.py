"""merchant_flow14 商家分阶段入驻与协议归档

Revision ID: merchant_flow14
Revises: compliance_0013
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "merchant_flow14"
down_revision: Union[str, Sequence[str], None] = "compliance_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shop_agreements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("agreement_number", sa.String(length=64), nullable=False),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_by_user_id", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merchant_signed_asset_id", sa.String(length=32), nullable=True),
        sa.Column("merchant_signed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("merchant_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("platform_signed_asset_id", sa.String(length=32), nullable=True),
        sa.Column("platform_signed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("platform_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_asset_id", sa.String(length=32), nullable=True),
        sa.Column("archived_by_user_id", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generated_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["merchant_signed_asset_id"], ["file_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["merchant_signed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["platform_signed_asset_id"], ["file_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["platform_signed_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["final_asset_id"], ["file_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["archived_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agreement_number", name="uq_shop_agreement_number"),
    )
    op.create_index("ix_shop_agreements_shop_id", "shop_agreements", ["shop_id"])

    with op.batch_alter_table("mall_shops") as batch_op:
        batch_op.add_column(
            sa.Column(
                "onboarding_stage",
                sa.String(length=40),
                server_default="qualification_submitted",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("current_agreement_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_shop_current_agreement",
            "shop_agreements",
            ["current_agreement_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_mall_shops_onboarding_stage", ["onboarding_stage"])

    op.execute(
        "UPDATE mall_shops SET onboarding_stage = CASE "
        "WHEN status = 'APPROVED' OR status = 'CLOSED' THEN 'approved' "
        "WHEN status = 'REJECTED' THEN 'rejected' "
        "ELSE 'qualification_submitted' END"
    )


def downgrade() -> None:
    with op.batch_alter_table("mall_shops") as batch_op:
        batch_op.drop_index("ix_mall_shops_onboarding_stage")
        batch_op.drop_constraint("fk_shop_current_agreement", type_="foreignkey")
        batch_op.drop_column("current_agreement_id")
        batch_op.drop_column("onboarding_stage")
    op.drop_index("ix_shop_agreements_shop_id", table_name="shop_agreements")
    op.drop_table("shop_agreements")
