"""payment active attempt

Revision ID: pay_active_0009
Revises: audit_0008
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "pay_active_0009"
down_revision: Union[str, Sequence[str], None] = "audit_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mall_payments",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT order_no, id, status FROM mall_payments "
            "ORDER BY order_no, CASE WHEN status = 'SUCCESS' THEN 0 ELSE 1 END, id DESC"
        )
    ).mappings()
    seen: set[str] = set()
    for row in rows:
        if row["order_no"] not in seen:
            seen.add(row["order_no"])
            continue
        bind.execute(
            sa.text(
                "UPDATE mall_payments SET is_active = false, "
                "status = CASE WHEN status = 'UNPAID' THEN 'FAILED' ELSE status END "
                "WHERE id = :id"
            ),
            {"id": row["id"]},
        )

    op.create_index(
        "uq_mall_payments_active_order",
        "mall_payments",
        ["order_no"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active = 1"),
    )
def downgrade() -> None:
    op.drop_index("uq_mall_payments_active_order", table_name="mall_payments")
    op.drop_column("mall_payments", "is_active")
