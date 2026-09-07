"""商城端到端测试所需的真实合规流程样板。"""

from __future__ import annotations

from datetime import date, timedelta
import hashlib


def upload_compliance_asset(test_client, headers: dict[str, str], filename: str) -> str:
    content = b"test-compliance-material"
    intent = test_client.post(
        "/api/files/upload-intents",
        json={"filename": filename, "size_bytes": len(content)},
        headers=headers,
    )
    assert intent.status_code == 201, intent.text
    payload = intent.json()
    upload_url = payload["upload"]["url"]
    uploaded = test_client.post(
        f"/api{upload_url}",
        files={"file": (filename, content, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 204, uploaded.text
    asset_id = payload["asset"]["id"]
    completed = test_client.post(
        f"/api/files/{asset_id}/complete", headers=headers
    )
    assert completed.status_code == 200, completed.text
    return asset_id


def shop_application_payload(
    test_client,
    headers: dict[str, str],
    *,
    name: str,
    credit_seed: str | None = None,
) -> dict:
    credit_code = hashlib.sha256((credit_seed or name).encode()).hexdigest()[:18].upper()
    return {
        "name": name,
        "description": "自动化测试店铺",
        "real_name": "测试商家",
        "identity_number": "110101199001011234",
        "legal_entity_name": f"{name}有限公司",
        "unified_social_credit_code": credit_code,
        "legal_representative": "测试法人",
        "registered_address": "浙江省杭州市测试路一号",
        "business_address": "浙江省杭州市经营路二号",
        "contact_phone": "13800138000",
        "business_license_valid_until": (date.today() + timedelta(days=365)).isoformat(),
        "business_license_long_term": False,
        "business_license_asset_id": upload_compliance_asset(
            test_client, headers, "business-license.png"
        ),
        "identity_front_asset_id": upload_compliance_asset(
            test_client, headers, "identity-front.png"
        ),
        "identity_back_asset_id": upload_compliance_asset(
            test_client, headers, "identity-back.png"
        ),
    }


def shop_review_payload(test_client, headers: dict[str, str], *, approved: bool) -> dict:
    return {
        "approved": approved,
        "reject_reason": None if approved else "企业核验信息不一致",
        "evidence_asset_id": upload_compliance_asset(
            test_client, headers, "registry-evidence.png"
        ),
        "registration_status": "存续",
        "verification_source": "国家企业信用信息公示系统",
        "entity_name_matches": approved,
        "credit_code_matches": approved,
        "legal_representative_matches": approved,
        "registration_status_valid": approved,
        "registered_address_matches": approved,
        "business_scope_matches": approved,
        "note": "自动化测试核验记录",
    }


def complete_shop_onboarding(
    test_client,
    seller_headers: dict[str, str],
    admin_headers: dict[str, str],
    shop_id: int,
) -> dict:
    """按生产约束完成在线签约入驻，并返回最终店铺响应。"""
    reviewed = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/review",
        json=shop_review_payload(test_client, admin_headers, approved=True),
        headers=admin_headers,
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["onboarding_stage"] == "agreement_generated"
    assert reviewed.json()["current_agreement"]["signature_mode"] == "online_click"

    generated = test_client.get(
        "/api/mall/seller/shop/agreement", headers=seller_headers
    )
    assert generated.status_code == 200, generated.text
    agreement = generated.json()
    assert "内容 SHA-256" not in agreement["content_markdown"]
    assert "确认签署电子协议" in agreement["content_markdown"]
    assert len(agreement["draft_content_sha256"]) == 64
    assert agreement["signature_mode"] == "online_click"

    accepted = test_client.post(
        "/api/mall/seller/shop/agreement/accept",
        json={
            "agreement_number": agreement["agreement_number"],
            "document_version": agreement["document_version"],
            "draft_content_sha256": agreement["draft_content_sha256"],
            "confirmed": True,
        },
        headers=seller_headers,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["onboarding_stage"] == "agreement_archived"
    current = accepted.json()["current_agreement"]
    assert current["merchant_signed_asset_id"] is None
    assert current["platform_signed_asset_id"] is None
    assert current["final_asset_id"] is None
    assert current["merchant_signed_by_user_id"] is not None
    assert current["merchant_signed_at"] is not None

    approved = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/approve",
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["onboarding_stage"] == "approved"
    return approved.json()
