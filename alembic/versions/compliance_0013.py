"""compliance_0013 网站许可整改数据闭环

Revision ID: compliance_0013
Revises: complaint_0012

新增协议接受、发布者实名、材料引用、企业资质复核数据，并将无法证明
真实主体的旧公开数据安全下线。迁移不会补造任何协议或审核记录。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "compliance_0013"
down_revision: Union[str, Sequence[str], None] = "complaint_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "legal_acceptances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_ip", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "document_type", "document_version", name="uq_legal_acceptance"
        ),
    )
    op.create_index(
        "ix_legal_acceptances_user_id", "legal_acceptances", ["user_id"]
    )

    op.create_table(
        "file_asset_references",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retain_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["file_assets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_id",
            "resource_type",
            "resource_id",
            "purpose",
            name="uq_file_asset_reference",
        ),
    )
    op.create_index(
        "ix_file_asset_references_asset_id", "file_asset_references", ["asset_id"]
    )

    verification_status = sa.Enum(
        "PENDING", "APPROVED", "REJECTED", name="publisherverificationstatus"
    )
    op.create_table(
        "information_publisher_verifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("real_name", sa.String(length=100), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("document_number_encrypted", sa.Text(), nullable=False),
        sa.Column("document_number_masked", sa.String(length=64), nullable=False),
        sa.Column("document_front_asset_id", sa.String(length=32), nullable=False),
        sa.Column("document_back_asset_id", sa.String(length=32), nullable=True),
        sa.Column("document_valid_until", sa.Date(), nullable=True),
        sa.Column(
            "document_long_term", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("status", verification_status, nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["document_front_asset_id"], ["file_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["document_back_asset_id"], ["file_assets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_information_publisher_verifications_user_id",
        "information_publisher_verifications",
        ["user_id"],
    )
    op.create_index(
        "uq_info_verify_pending",
        "information_publisher_verifications",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'PENDING'"),
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    with op.batch_alter_table("information_posts") as batch_op:
        batch_op.add_column(
            sa.Column("publisher_verification_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("withdrawn_reason", sa.String(length=300), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_info_post_verification",
            "information_publisher_verifications",
            ["publisher_verification_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_info_post_reviewer",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_information_posts_publisher_verification_id",
            ["publisher_verification_id"],
        )

    op.create_table(
        "shop_qualification_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("verification_source", sa.String(length=200), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=False),
        sa.Column("evidence_asset_id", sa.String(length=32), nullable=False),
        sa.Column("registration_status", sa.String(length=100), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["mall_shops.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_asset_id"], ["file_assets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_shop_qualification_reviews_shop_id",
        "shop_qualification_reviews",
        ["shop_id"],
    )

    with op.batch_alter_table("mall_shops") as batch_op:
        batch_op.alter_column(
            "identity_number",
            existing_type=sa.String(length=32),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.add_column(
            sa.Column("identity_number_masked", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("legal_entity_name", sa.String(length=200), nullable=True)
        )
        batch_op.add_column(
            sa.Column("unified_social_credit_code", sa.String(length=18), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "unified_social_credit_code_masked", sa.String(length=18), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("legal_representative", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("registered_address", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("business_address", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("contact_phone", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(sa.Column("business_license_valid_until", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "business_license_long_term",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column("merchant_agreement_version", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("merchant_agreement_asset_id", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("agreement_accepted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("qualification_valid_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_qualification_review_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "last_qualification_checked_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column("registration_status", sa.String(length=100), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_mall_shops_credit_code", ["unified_social_credit_code"]
        )
        batch_op.create_foreign_key(
            "fk_shop_last_qualification_review",
            "shop_qualification_reviews",
            ["last_qualification_review_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_mall_shops_unified_social_credit_code",
            ["unified_social_credit_code"],
        )
        batch_op.create_index(
            "ix_mall_shops_qualification_valid_until", ["qualification_valid_until"]
        )

    # 缺少真实核验快照的历史数据不可继续公开；不为其补造审核或协议记录。
    op.execute(
        sa.text(
            "UPDATE information_posts "
            "SET status = 'REJECTED', approved_at = NULL, withdrawn_at = CURRENT_TIMESTAMP, "
            "withdrawn_reason = :reason, reject_reason = :reason "
            "WHERE status = 'APPROVED' AND publisher_verification_id IS NULL"
        ).bindparams(reason="历史数据缺少发布者实名核验，已下线待重新提交")
    )
    op.execute(
        sa.text(
            "UPDATE mall_shops SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP, "
            "reject_reason = :reason WHERE status = 'APPROVED' "
            "AND last_qualification_review_id IS NULL"
        ).bindparams(reason="历史店铺缺少企业资质核验材料，已停止公开")
    )
    op.execute(
        sa.text(
            "UPDATE mall_goods SET status = 'OFF' WHERE status = 'ON' AND shop_id IN "
            "(SELECT id FROM mall_shops WHERE status = 'CLOSED')"
        )
    )


def downgrade() -> None:
    # 降级只恢复结构，不伪造或恢复已经因缺少材料而下线的业务数据。
    with op.batch_alter_table("mall_shops") as batch_op:
        batch_op.drop_index("ix_mall_shops_qualification_valid_until")
        batch_op.drop_index("ix_mall_shops_unified_social_credit_code")
        batch_op.drop_constraint("fk_shop_last_qualification_review", type_="foreignkey")
        batch_op.drop_constraint("uq_mall_shops_credit_code", type_="unique")
        for column in (
            "registration_status",
            "last_qualification_checked_at",
            "last_qualification_review_id",
            "qualification_valid_until",
            "agreement_accepted_at",
            "merchant_agreement_asset_id",
            "merchant_agreement_version",
            "business_license_long_term",
            "business_license_valid_until",
            "contact_phone",
            "business_address",
            "registered_address",
            "legal_representative",
            "unified_social_credit_code_masked",
            "unified_social_credit_code",
            "legal_entity_name",
            "identity_number_masked",
        ):
            batch_op.drop_column(column)
        batch_op.alter_column(
            "identity_number",
            existing_type=sa.Text(),
            type_=sa.String(length=32),
            existing_nullable=True,
        )

    op.drop_index(
        "ix_shop_qualification_reviews_shop_id",
        table_name="shop_qualification_reviews",
    )
    op.drop_table("shop_qualification_reviews")

    with op.batch_alter_table("information_posts") as batch_op:
        batch_op.drop_index("ix_information_posts_publisher_verification_id")
        batch_op.drop_constraint("fk_info_post_reviewer", type_="foreignkey")
        batch_op.drop_constraint("fk_info_post_verification", type_="foreignkey")
        batch_op.drop_column("withdrawn_reason")
        batch_op.drop_column("withdrawn_at")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by_user_id")
        batch_op.drop_column("publisher_verification_id")

    op.drop_index(
        "uq_info_verify_pending", table_name="information_publisher_verifications"
    )
    op.drop_index(
        "ix_information_publisher_verifications_user_id",
        table_name="information_publisher_verifications",
    )
    op.drop_table("information_publisher_verifications")
    op.drop_index("ix_file_asset_references_asset_id", table_name="file_asset_references")
    op.drop_table("file_asset_references")
    op.drop_index("ix_legal_acceptances_user_id", table_name="legal_acceptances")
    op.drop_table("legal_acceptances")
