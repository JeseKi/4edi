"""重命名协议定稿哈希并增加最终签署文件哈希

Revision ID: agreement_hash15
Revises: merchant_flow14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "agreement_hash15"
down_revision: Union[str, Sequence[str], None] = "merchant_flow14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("shop_agreements") as batch_op:
        batch_op.alter_column(
            "content_sha256",
            new_column_name="draft_content_sha256",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column("final_file_sha256", sa.String(length=64), nullable=True)
        )

def downgrade() -> None:
    with op.batch_alter_table("shop_agreements") as batch_op:
        batch_op.drop_column("final_file_sha256")
        batch_op.alter_column(
            "draft_content_sha256",
            new_column_name="content_sha256",
            existing_type=sa.String(length=64),
            existing_nullable=False,
        )
