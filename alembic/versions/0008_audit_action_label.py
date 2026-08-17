"""audit_action_label

Revision ID: audit_0008
Revises: fav_0007
Create Date: 2026-08-17 15:10:00.000000

audit_events 补充 action_label 列（审计动作中文标签，模型已有该字段，
早期建表迁移遗漏，导致低优先级审计批量写入持续失败）。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "audit_0008"
down_revision: Union[str, Sequence[str], None] = "fav_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "audit_events",
        sa.Column("action_label", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("audit_events", "action_label")
