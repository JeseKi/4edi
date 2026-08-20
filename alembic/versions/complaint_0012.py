"""complaint_0012 用户投诉

Revision ID: complaint_0012
Revises: information_0011

新增用户投诉功能包数据表：投诉记录。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "complaint_0012"
down_revision: Union[str, Sequence[str], None] = "information_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contact", sa.String(length=120), nullable=True),
        sa.Column("reporter_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.Enum("PENDING", "RESOLVED", name="complaintstatus"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_complaints_status_created",
        "complaints",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_complaints_status_created", table_name="complaints")
    op.drop_table("complaints")
