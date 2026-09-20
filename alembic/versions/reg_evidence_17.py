"""增加可吊销监管取证共享链接

Revision ID: reg_evidence_17
Revises: shop_scope_160
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "reg_evidence_17"
down_revision: Union[str, Sequence[str], None] = "shop_scope_160"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regulatory_evidence_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_hint", sa.String(length=8), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_regulatory_evidence_links_token_hash",
        "regulatory_evidence_links",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_reg_evidence_resource",
        "regulatory_evidence_links",
        ["evidence_type", "resource_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reg_evidence_resource", table_name="regulatory_evidence_links"
    )
    op.drop_index(
        "ix_regulatory_evidence_links_token_hash",
        table_name="regulatory_evidence_links",
    )
    op.drop_table("regulatory_evidence_links")
