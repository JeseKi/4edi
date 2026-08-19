"""information_0011 分类信息发布

Revision ID: information_0011
Revises: shop_docs_0010

新增信息发布功能包数据表：分类信息发布记录。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "information_0011"
down_revision: Union[str, Sequence[str], None] = "shop_docs_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "information_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("price", sa.String(length=50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("contact_name", sa.String(length=50), nullable=False),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("poster_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="informationstatus"), nullable=False
        ),
        sa.Column("reject_reason", sa.String(length=200), nullable=True),
        sa.Column("is_top", sa.Boolean(), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["poster_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_information_posts_poster_user_id",
        "information_posts",
        ["poster_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_information_posts_status_created",
        "information_posts",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_information_posts_category_status",
        "information_posts",
        ["category", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_information_posts_category_status", table_name="information_posts"
    )
    op.drop_index(
        "ix_information_posts_status_created", table_name="information_posts"
    )
    op.drop_index(
        "ix_information_posts_poster_user_id", table_name="information_posts"
    )
    op.drop_table("information_posts")
