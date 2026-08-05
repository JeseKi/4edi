# -*- coding: utf-8 -*-
"""Regression tests for high-priority semantic audit events."""

from src.server.audit.models import AuditEvent


def _admin_headers(test_client) -> dict[str, str]:
    response = test_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_user_changes_have_target_and_safe_diff(
    test_client,
    test_db_session,
    init_test_database,
):
    headers = _admin_headers(test_client)
    create_response = test_client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "username": "audited_member",
            "email": "audited_member@example.com",
            "password": "Password123",
            "role": "user",
            "status": "active",
        },
    )
    assert create_response.status_code == 201, create_response.text
    user_id = create_response.json()["id"]

    create_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.action == "admin.user.create")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert create_event is not None
    assert create_event.resource_type == "user"
    assert create_event.resource_id == str(user_id)
    assert create_event.priority == "high"
    assert '"password"' not in create_event.detail_json

    update_response = test_client.patch(
        f"/api/admin/users/{user_id}",
        headers=headers,
        json={"role": "admin", "password": "ChangedPassword123"},
    )
    assert update_response.status_code == 200, update_response.text

    update_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.action == "admin.user.update")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert update_event is not None
    assert update_event.resource_id == str(user_id)
    assert '"security_operation": "password_update"' in update_event.detail_json
    assert "ChangedPassword123" not in update_event.detail_json


def test_oauth_client_operations_have_semantic_audit_context(
    test_client,
    test_db_session,
    init_test_database,
):
    headers = _admin_headers(test_client)
    response = test_client.post(
        "/api/oauth-provider/clients",
        headers=headers,
        json={
            "name": "Audited OAuth App",
            "redirect_uris": ["https://example.com/callback"],
            "allowed_scopes": ["profile:read"],
        },
    )
    assert response.status_code == 201, response.text
    client_id = response.json()["client_id"]

    event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.action == "admin.oauth_client.create")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert event is not None
    assert event.resource_type == "oauth_client"
    assert event.resource_id == client_id
    assert event.priority == "high"
    assert response.json()["client_secret"] not in event.detail_json
