from __future__ import annotations

from http import HTTPStatus

from sqlalchemy.orm import Session

from src.server.audit.models import AuditEvent
from src.server.config import global_config


def _login_admin(test_client):
    response = test_client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == HTTPStatus.OK, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_file_operations_record_semantic_audit_context(
    test_client,
    test_db_session: Session,
    init_test_database,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(global_config.files, "storage_driver", "local")
    monkeypatch.setattr(global_config.files, "local_root", tmp_path / "uploads")
    headers = _login_admin(test_client)

    intent_response = test_client.post(
        "/api/files/upload-intents",
        json={"filename": "hello.txt", "size_bytes": 5},
        headers=headers,
    )
    assert intent_response.status_code == HTTPStatus.CREATED, intent_response.text
    asset_id = intent_response.json()["asset"]["id"]

    intent_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.action == "files.upload_intent.create")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert intent_event is not None
    assert intent_event.resource_type == "file_asset"
    assert intent_event.resource_id == asset_id
    assert '"size_bytes": 5' in intent_event.detail_json
    assert intent_event.actor_username == "admin"

    upload_response = test_client.post(
        f"/api{intent_response.json()['upload']['url']}",
        files={"file": ("hello.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert upload_response.status_code == HTTPStatus.NO_CONTENT, upload_response.text

    upload_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.action == "files.content.upload")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert upload_event is not None
    assert upload_event.resource_id == asset_id


def test_local_file_upload_download_and_delete(
    test_client, init_test_database, monkeypatch, tmp_path
):
    monkeypatch.setattr(global_config.files, "storage_driver", "local")
    monkeypatch.setattr(global_config.files, "local_root", tmp_path / "uploads")
    headers = _login_admin(test_client)

    intent_response = test_client.post(
        "/api/files/upload-intents",
        json={"filename": "hello.txt", "size_bytes": 5},
        headers=headers,
    )
    assert intent_response.status_code == HTTPStatus.CREATED, intent_response.text
    intent = intent_response.json()
    assert intent["upload"]["kind"] == "local"

    upload_response = test_client.post(
        f"/api{intent['upload']['url']}",
        files={"file": ("hello.txt", b"hello", "text/plain")},
        headers=headers,
    )
    assert upload_response.status_code == HTTPStatus.NO_CONTENT, upload_response.text

    complete_response = test_client.post(
        f"/api/files/{intent['asset']['id']}/complete", headers=headers
    )
    assert complete_response.status_code == HTTPStatus.OK, complete_response.text
    assert complete_response.json()["status"] == "available"

    download_response = test_client.get(
        f"/api/files/{intent['asset']['id']}/download", headers=headers
    )
    assert download_response.status_code == HTTPStatus.OK
    assert download_response.content == b"hello"
    assert "attachment" in download_response.headers["content-disposition"]

    delete_response = test_client.delete(f"/api/files/{intent['asset']['id']}", headers=headers)
    assert delete_response.status_code == HTTPStatus.OK
    assert delete_response.json()["status"] in {"deletion_pending", "deleted"}
