"""信息发布测试使用的协议与实名资格样板。"""

from __future__ import annotations

from src.server.auth.models import LegalAcceptance, User
from src.server.information.models import (
    PublisherVerification,
    PublisherVerificationStatus,
)
from src.server.mall.tests._compliance_helpers import upload_compliance_asset


def qualify_user_in_db(db, user: User) -> PublisherVerification:
    for document_type in ("user_agreement", "privacy_policy"):
        db.add(
            LegalAcceptance(
                user_id=user.id,
                document_type=document_type,
                document_version="2026-09-02",
            )
        )
    verification = PublisherVerification(
        user_id=user.id,
        real_name=user.name or user.username,
        document_type="resident_identity_card",
        document_number_encrypted="v1:test-only",
        document_number_masked="110***********1234",
        document_front_asset_id=f"front-{user.id}",
        document_back_asset_id=f"back-{user.id}",
        document_valid_until=None,
        document_long_term=True,
        status=PublisherVerificationStatus.APPROVED,
        reviewer_user_id=user.id,
    )
    db.add(verification)
    db.flush()
    return verification


def qualify_user_via_api(test_client, user_headers: dict[str, str], admin_headers: dict[str, str]) -> int:
    front = upload_compliance_asset(test_client, user_headers, "publisher-front.png")
    back = upload_compliance_asset(test_client, user_headers, "publisher-back.png")
    submitted = test_client.post(
        "/api/information/verification",
        headers=user_headers,
        json={
            "real_name": "测试发布者",
            "document_type": "resident_identity_card",
            "document_number": "110101199001011234",
            "document_front_asset_id": front,
            "document_back_asset_id": back,
            "document_long_term": True,
        },
    )
    assert submitted.status_code == 201, submitted.text
    verification_id = submitted.json()["id"]
    reviewed = test_client.post(
        f"/api/information/admin/verifications/{verification_id}/review",
        headers=admin_headers,
        json={"approved": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    return verification_id
