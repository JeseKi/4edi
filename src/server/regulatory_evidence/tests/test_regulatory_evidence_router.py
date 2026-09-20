from __future__ import annotations

import hashlib

from src.server.auth.tests._auth_router_helpers import _auth_headers, _register_user
from src.server.information.tests._compliance_helpers import qualify_user_via_api
from src.server.mall.tests._compliance_helpers import (
    complete_shop_onboarding,
    shop_application_payload,
)
from src.server.regulatory_evidence.models import RegulatoryEvidenceLink


def _login(test_client, *, username: str, password: str = "Password123"):
    response = test_client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return _auth_headers(response.json()["access_token"])


def _login_admin(test_client):
    return _login(test_client, username="admin", password="admin123")


def _token_headers(token: str) -> dict[str, str]:
    return {"X-Regulatory-Evidence-Token": token}


def test_publisher_evidence_link_is_scoped_hashed_and_revocable(
    test_client, test_db_session, init_test_database
):
    _register_user(
        test_client,
        username="evidence-publisher",
        email="evidence-publisher@example.com",
    )
    publisher_headers = _login(test_client, username="evidence-publisher")
    admin_headers = _login_admin(test_client)
    verification_id = qualify_user_via_api(
        test_client, publisher_headers, admin_headers
    )

    created_post = test_client.post(
        "/api/information",
        headers=publisher_headers,
        json={
            "category": "mini_program",
            "title": "监管核验测试信息",
            "price": "面议",
            "contact_name": "测试人员",
            "contact_phone": "13800138000",
            "content": "用于验证监管核验链接仅可查看指定证据。",
        },
    )
    assert created_post.status_code == 201, created_post.text

    unauthorized = test_client.post(
        "/api/regulatory-evidence/admin/links",
        json={
            "evidence_type": "publisher_verification",
            "resource_id": verification_id,
        },
    )
    assert unauthorized.status_code == 401

    created = test_client.post(
        "/api/regulatory-evidence/admin/links",
        headers=admin_headers,
        json={
            "evidence_type": "publisher_verification",
            "resource_id": verification_id,
        },
    )
    assert created.status_code == 201, created.text
    link_data = created.json()
    token = link_data["token"]
    assert len(token) == 32
    assert link_data["share_path"] == f"/regulatory-evidence#{token}"

    stored = test_db_session.get(RegulatoryEvidenceLink, link_data["id"])
    assert stored is not None
    assert stored.token_hash == hashlib.sha256(token.encode("ascii")).hexdigest()
    assert token not in stored.token_hash

    public = test_client.get(
        "/api/regulatory-evidence", headers=_token_headers(token)
    )
    assert public.status_code == 200, public.text
    payload = public.json()
    assert payload["evidence_type"] == "publisher_verification"
    evidence = payload["publisher_verification"]
    assert evidence["verification"]["id"] == verification_id
    assert evidence["posts"][0]["id"] == created_post.json()["id"]
    assert evidence["posts"][0]["content"] == "用于验证监管核验链接仅可查看指定证据。"
    assert evidence["posts"][0]["contact_phone"] == "138****8000"
    assert "poster_user_id" not in evidence["posts"][0]
    assert public.headers["cache-control"] == "no-store, private"
    assert public.headers["x-robots-tag"] == "noindex, nofollow, noarchive"

    front_asset_id = evidence["verification"]["document_front_asset_id"]
    material = test_client.get(
        f"/api/regulatory-evidence/assets/{front_asset_id}",
        headers=_token_headers(token),
    )
    assert material.status_code == 200, material.text
    assert material.content == b"test-compliance-material"
    assert material.headers["cache-control"] == "no-store, private"

    wrong_asset = test_client.get(
        "/api/regulatory-evidence/assets/00000000000000000000000000000000",
        headers=_token_headers(token),
    )
    assert wrong_asset.status_code == 404

    links = test_client.get(
        "/api/regulatory-evidence/admin/links",
        headers=admin_headers,
        params={
            "evidence_type": "publisher_verification",
            "resource_id": verification_id,
        },
    )
    assert links.status_code == 200, links.text
    assert links.json()[0]["access_count"] == 1

    revoked = test_client.post(
        f"/api/regulatory-evidence/admin/links/{link_data['id']}/revoke",
        headers=admin_headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked_at"] is not None

    after_revoke = test_client.get(
        "/api/regulatory-evidence", headers=_token_headers(token)
    )
    assert after_revoke.status_code == 404


def test_shop_evidence_link_includes_business_license(
    test_client, init_test_database
):
    _register_user(
        test_client, username="evidence-seller", email="evidence-seller@example.com"
    )
    seller_headers = _login(test_client, username="evidence-seller")
    admin_headers = _login_admin(test_client)
    application = shop_application_payload(
        test_client, seller_headers, name="监管核验店铺"
    )
    applied = test_client.post(
        "/api/mall/seller/shop/apply",
        json=application,
        headers=seller_headers,
    )
    assert applied.status_code == 201, applied.text
    shop_id = applied.json()["id"]
    complete_shop_onboarding(test_client, seller_headers, admin_headers, shop_id)

    created = test_client.post(
        "/api/regulatory-evidence/admin/links",
        headers=admin_headers,
        json={"evidence_type": "shop_qualification", "resource_id": shop_id},
    )
    assert created.status_code == 201, created.text
    token = created.json()["token"]

    public = test_client.get(
        "/api/regulatory-evidence", headers=_token_headers(token)
    )
    assert public.status_code == 200, public.text
    evidence = public.json()["shop_qualification"]
    assert evidence["shop"]["id"] == shop_id
    assert evidence["shop"]["business_license_asset_id"] == application[
        "business_license_asset_id"
    ]
    assert "contact_phone" not in evidence["shop"]
    assert "current_agreement" not in evidence["shop"]
    assert evidence["qualification_reviews"]

    license_response = test_client.get(
        f"/api/regulatory-evidence/assets/{application['business_license_asset_id']}",
        headers=_token_headers(token),
    )
    assert license_response.status_code == 200, license_response.text
    assert license_response.content == b"test-compliance-material"
