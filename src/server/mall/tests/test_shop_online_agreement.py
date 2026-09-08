"""商家在线签约流程及历史文件协议兼容测试。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.server.audit.models import AuditEvent
from src.server.auth.models import LegalAcceptance
from src.server.compliance.config import compliance_config
from src.server.mall.models import Shop, ShopAgreement, ShopQualificationReview
from src.server.mall.tests._compliance_helpers import (
    shop_application_payload,
    shop_review_payload,
    upload_compliance_asset,
)
from src.server.mall.tests.test_mall_router import _login, _login_admin, _register


def _prepare_online_agreement(test_client, *, username: str = "online-seller"):
    seller_headers = _login(
        test_client,
        username=_register(
            test_client, username=username, email=f"{username}@example.com"
        ),
    )
    admin_headers = _login_admin(test_client)
    applied = test_client.post(
        "/api/mall/seller/shop/apply",
        json=shop_application_payload(
            test_client, seller_headers, name=f"{username}店铺"
        ),
        headers=seller_headers,
    )
    assert applied.status_code == 201, applied.text
    shop_id = applied.json()["id"]
    reviewed = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/review",
        json=shop_review_payload(test_client, admin_headers, approved=True),
        headers=admin_headers,
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["onboarding_stage"] == "agreement_generated"
    agreement_response = test_client.get(
        "/api/mall/seller/shop/agreement", headers=seller_headers
    )
    assert agreement_response.status_code == 200, agreement_response.text
    return seller_headers, admin_headers, shop_id, agreement_response.json()


def _acceptance_payload(agreement: dict) -> dict:
    return {
        "agreement_number": agreement["agreement_number"],
        "document_version": agreement["document_version"],
        "draft_content_sha256": agreement["draft_content_sha256"],
        "confirmed": True,
    }


def test_preapproval_generates_and_online_acceptance_archives_agreement(
    test_client, test_db_session, init_test_database
):
    seller_headers, admin_headers, shop_id, agreement = _prepare_online_agreement(
        test_client
    )
    assert agreement["document_version"] == "2026-09-07"
    assert agreement["signature_mode"] == "online_click"
    assert agreement["status"] == "generated"
    assert "甲方（平台）" in agreement["content_markdown"]
    assert "乙方（商家）" in agreement["content_markdown"]
    assert "内容 SHA-256" not in agreement["content_markdown"]
    assert "暂不接受依法需取得专项行政许可" in agreement["content_markdown"]

    admin_agreement = test_client.get(
        f"/api/mall/admin/shops/{shop_id}/agreement", headers=admin_headers
    )
    assert admin_agreement.status_code == 200, admin_agreement.text
    assert admin_agreement.json()["content_markdown"] == agreement["content_markdown"]

    before_approval = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/approve", headers=admin_headers
    )
    assert before_approval.status_code == 409

    headers = {**seller_headers, "User-Agent": "online-agreement-test/1.0"}
    accepted = test_client.post(
        "/api/mall/seller/shop/agreement/accept",
        json=_acceptance_payload(agreement),
        headers=headers,
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["onboarding_stage"] == "agreement_archived"
    assert body["status"] == "pending"
    assert body["agreement_accepted_at"] is not None
    assert body["current_agreement"]["status"] == "archived"
    assert body["current_agreement"]["merchant_signed_asset_id"] is None
    assert body["current_agreement"]["platform_signed_asset_id"] is None
    assert body["current_agreement"]["final_asset_id"] is None
    signed_agreement = test_client.get(
        "/api/mall/seller/shop/agreement", headers=seller_headers
    )
    assert signed_agreement.status_code == 200
    assert signed_agreement.json()["merchant_signed_account"] == "online-seller"

    first_accepted_at = body["agreement_accepted_at"]
    repeated = test_client.post(
        "/api/mall/seller/shop/agreement/accept",
        json=_acceptance_payload(agreement),
        headers=headers,
    )
    assert repeated.status_code == 200, repeated.text
    assert datetime.fromisoformat(
        repeated.json()["agreement_accepted_at"].replace("Z", "+00:00")
    ).replace(tzinfo=None) == datetime.fromisoformat(
        first_accepted_at.replace("Z", "+00:00")
    ).replace(tzinfo=None)

    test_db_session.expire_all()
    stored = test_db_session.get(ShopAgreement, agreement["id"])
    assert stored is not None
    assert stored.acceptance_ip
    assert stored.acceptance_user_agent == "online-agreement-test/1.0"
    assert stored.merchant_signed_by_user_id is not None
    assert stored.merchant_signed_at == stored.archived_at
    assert test_db_session.query(LegalAcceptance).filter_by(
        user_id=stored.merchant_signed_by_user_id,
        document_type="merchant_agreement",
        document_version="2026-09-07",
    ).count() == 1
    assert test_db_session.query(AuditEvent).filter_by(
        action="mall.shop.agreement.accept",
        resource_id=str(agreement["id"]),
    ).count() >= 1

    approved = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"


def test_shop_application_requires_open_scope_confirmation(
    test_client, init_test_database
):
    seller_headers = _login(
        test_client,
        username=_register(
            test_client,
            username="scope-unconfirmed",
            email="scope-unconfirmed@example.com",
        ),
    )
    payload = shop_application_payload(
        test_client, seller_headers, name="范围声明测试店"
    )
    payload["special_license_not_required"] = False

    response = test_client.post(
        "/api/mall/seller/shop/apply", json=payload, headers=seller_headers
    )

    assert response.status_code == 422


def test_shop_preapproval_requires_admin_scope_check(
    test_client, init_test_database
):
    seller_headers = _login(
        test_client,
        username=_register(
            test_client,
            username="scope-admin-check",
            email="scope-admin-check@example.com",
        ),
    )
    admin_headers = _login_admin(test_client)
    applied = test_client.post(
        "/api/mall/seller/shop/apply",
        json=shop_application_payload(
            test_client, seller_headers, name="管理员范围核验测试店"
        ),
        headers=seller_headers,
    )
    assert applied.status_code == 201, applied.text
    payload = shop_review_payload(test_client, admin_headers, approved=True)
    payload["special_license_scope_allowed"] = False

    response = test_client.post(
        f"/api/mall/admin/shops/{applied.json()['id']}/review",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert "企业核验项目" in response.json()["detail"]


def test_special_license_category_is_hidden_and_cannot_receive_goods(
    test_client, init_test_database
):
    seller_headers, admin_headers, shop_id, agreement = _prepare_online_agreement(
        test_client, username="restricted-category"
    )
    accepted = test_client.post(
        "/api/mall/seller/shop/agreement/accept",
        json=_acceptance_payload(agreement),
        headers=seller_headers,
    )
    assert accepted.status_code == 200, accepted.text
    approved = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/approve", headers=admin_headers
    )
    assert approved.status_code == 200, approved.text
    category = test_client.post(
        "/api/mall/categories",
        json={
            "name": "需要专项许可的测试类目",
            "sort": 99,
            "requires_special_license": True,
        },
        headers=admin_headers,
    )
    assert category.status_code == 201, category.text
    category_id = category.json()["id"]

    categories = test_client.get("/api/mall/categories")
    assert categories.status_code == 200
    assert category_id not in {item["id"] for item in categories.json()}

    goods = test_client.post(
        "/api/mall/seller/goods",
        json={
            "category_id": category_id,
            "name": "不应允许创建的商品",
            "main_image": "/mall/goods-1.svg",
            "skus": [{"price_fen": 100, "stock": 1}],
        },
        headers=seller_headers,
    )
    assert goods.status_code == 422
    assert "首期暂不开放" in goods.json()["detail"]


def test_online_acceptance_rejects_changed_or_unauthorized_request(
    test_client, init_test_database
):
    seller_headers, _, _, agreement = _prepare_online_agreement(
        test_client, username="online-invalid"
    )
    other_headers = _login(
        test_client,
        username=_register(
            test_client, username="online-other", email="online-other@example.com"
        ),
    )
    denied = test_client.post(
        "/api/mall/seller/shop/agreement/accept",
        json=_acceptance_payload(agreement),
        headers=other_headers,
    )
    assert denied.status_code == 404

    for field, value in (
        ("agreement_number", "M-WRONG"),
        ("document_version", "1900-01-01"),
        ("draft_content_sha256", "0" * 64),
    ):
        payload = _acceptance_payload(agreement)
        payload[field] = value
        response = test_client.post(
            "/api/mall/seller/shop/agreement/accept",
            json=payload,
            headers=seller_headers,
        )
        assert response.status_code == 422, response.text

    unconfirmed = _acceptance_payload(agreement)
    unconfirmed["confirmed"] = False
    response = test_client.post(
        "/api/mall/seller/shop/agreement/accept",
        json=unconfirmed,
        headers=seller_headers,
    )
    assert response.status_code == 422

    legacy_upload = upload_compliance_asset(
        test_client, seller_headers, "not-required-online-agreement.pdf"
    )
    response = test_client.post(
        "/api/mall/seller/shop/agreement/merchant-sign",
        json={
            "agreement_number": agreement["agreement_number"],
            "document_version": agreement["document_version"],
            "merchant_signed_asset_id": legacy_upload,
            "confirmed": True,
        },
        headers=seller_headers,
    )
    assert response.status_code == 409
    assert "在线签约" in response.json()["detail"]


def test_online_acceptance_rejects_expired_preapproval(
    test_client, test_db_session, init_test_database
):
    seller_headers, _, shop_id, agreement = _prepare_online_agreement(
        test_client, username="online-expired"
    )
    test_db_session.expire_all()
    shop = test_db_session.get(Shop, shop_id)
    assert shop is not None and shop.last_qualification_review_id is not None
    review = test_db_session.get(
        ShopQualificationReview, shop.last_qualification_review_id
    )
    assert review is not None
    review.checked_at = datetime.now(timezone.utc) - timedelta(days=220)
    test_db_session.commit()

    response = test_client.post(
        "/api/mall/seller/shop/agreement/accept",
        json=_acceptance_payload(agreement),
        headers=seller_headers,
    )
    assert response.status_code == 409
    assert "资质预审已过期" in response.json()["detail"]


def test_platform_identity_is_required_before_preapproval_can_commit(
    test_client, monkeypatch, init_test_database
):
    seller_headers = _login(
        test_client,
        username=_register(
            test_client,
            username="online-platform-missing",
            email="online-platform-missing@example.com",
        ),
    )
    admin_headers = _login_admin(test_client)
    applied = test_client.post(
        "/api/mall/seller/shop/apply",
        json=shop_application_payload(
            test_client, seller_headers, name="平台主体缺失测试店"
        ),
        headers=seller_headers,
    )
    shop_id = applied.json()["id"]
    monkeypatch.setattr(compliance_config, "legal_entity_credit_code", "")

    response = test_client.post(
        f"/api/mall/admin/shops/{shop_id}/review",
        json=shop_review_payload(test_client, admin_headers, approved=True),
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert "平台统一社会信用代码未配置" in response.json()["detail"]
    shop = test_client.get("/api/mall/seller/shop", headers=seller_headers)
    assert shop.json()["onboarding_stage"] == "qualification_submitted"
    assert shop.json()["current_agreement_id"] is None


def test_uploaded_document_agreement_keeps_legacy_signing_entry(
    test_client, test_db_session, init_test_database
):
    seller_headers, _, shop_id, agreement = _prepare_online_agreement(
        test_client, username="legacy-document"
    )
    test_db_session.expire_all()
    stored = test_db_session.get(ShopAgreement, agreement["id"])
    assert stored is not None
    stored.signature_mode = "uploaded_document"
    test_db_session.commit()

    signed_asset_id = upload_compliance_asset(
        test_client, seller_headers, "legacy-signed-agreement.pdf"
    )
    signed = test_client.post(
        "/api/mall/seller/shop/agreement/merchant-sign",
        json={
            "agreement_number": agreement["agreement_number"],
            "document_version": agreement["document_version"],
            "merchant_signed_asset_id": signed_asset_id,
            "confirmed": True,
        },
        headers=seller_headers,
    )
    assert signed.status_code == 200, signed.text
    assert signed.json()["onboarding_stage"] == "merchant_signed"
    assert signed.json()["current_agreement"]["signature_mode"] == "uploaded_document"
    assert signed.json()["id"] == shop_id
