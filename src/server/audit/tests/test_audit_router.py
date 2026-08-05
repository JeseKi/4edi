# -*- coding: utf-8 -*-
"""Audit router and middleware tests."""

import json
import threading
from collections.abc import Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy.orm import Session

from src.server.audit.models import AuditEvent
from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config
from src.server.oauth.service import core
from src.server.providers.constants import PROVIDER_GITHUB_OAUTH
from src.server.providers.mock_server import server_host_port
from src.server.providers.runtime import (
    clear_provider_runtime_configs,
    update_provider_runtime_config,
)


def _login_admin(test_client):
    resp = test_client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == HTTPStatus.OK, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_write_request_audit_captures_success_and_failure(
    test_client,
    test_db_session: Session,
    init_test_database,
):
    headers = _login_admin(test_client)

    create_resp = test_client.post(
        "/api/example/items",
        json={"name": "audited_item"},
        headers={**headers, "X-Request-ID": "audit-test-request"},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text

    failure_resp = test_client.post("/api/example/items", json={"name": "blocked"})
    assert failure_resp.status_code == HTTPStatus.UNAUTHORIZED

    success_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.path == "/api/example/items", AuditEvent.outcome == "success")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert success_event is not None
    assert success_event.actor_username == "admin"
    assert success_event.method == "POST"
    assert success_event.http_status_code == HTTPStatus.CREATED

    failure_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.path == "/api/example/items", AuditEvent.outcome == "failure")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert failure_event is not None
    assert failure_event.actor_user_id is None
    assert failure_event.http_status_code == HTTPStatus.UNAUTHORIZED


def test_admin_can_query_audit_events(
    test_client,
    init_test_database,
):
    headers = _login_admin(test_client)

    resp = test_client.get("/api/admin/audit-events?page=1&page_size=5", headers=headers)

    assert resp.status_code == HTTPStatus.OK, resp.text
    payload = resp.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["detail"] is not None


def test_audit_query_requires_audit_scope(test_client, test_db_session: Session):
    admin = User(
        username="audit_read_limited",
        email="audit_read_limited@example.com",
        role=UserRole.ADMIN,
        scope_overrides=auth_service.serialize_scopes(
            [auth_service.SCOPE_ADMIN_USERS_READ]
        ),
    )
    admin.set_password("Password123")
    test_db_session.add(admin)
    test_db_session.commit()
    test_db_session.refresh(admin)

    token = auth_service.create_access_token(
        {"sub": admin.username, "scope": auth_service.get_user_scopes(admin)}
    )
    resp = test_client.get(
        "/api/admin/audit-events",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert resp.json()["detail"]["required_scopes"] == [
        auth_service.SCOPE_ADMIN_AUDIT_READ
    ]


def test_get_request_audit_captures_target_and_actor(
    test_client,
    test_db_session: Session,
    init_test_database,
):
    headers = _login_admin(test_client)
    create_resp = test_client.post(
        "/api/example/items",
        json={"name": "audited_read_item"},
        headers=headers,
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    item_id = create_resp.json()["id"]

    get_resp = test_client.get(
        f"/api/example/items/{item_id}",
        headers={**headers, "X-Request-ID": "audit-get-request"},
    )
    assert get_resp.status_code == HTTPStatus.OK, get_resp.text

    event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.path == f"/api/example/items/{item_id}")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert event is not None
    assert event.method == "GET"
    assert event.outcome == "success"
    assert event.http_status_code == HTTPStatus.OK
    assert event.actor_username == "admin"
    assert event.resource_type == "items"
    assert event.resource_id == str(item_id)
    assert event.request_id == "audit-get-request"
    assert event.client_ip is not None


def test_public_get_api_request_is_audited(test_client, test_db_session: Session):
    resp = test_client.get("/api/example/ping")
    assert resp.status_code == HTTPStatus.OK, resp.text

    event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.path == "/api/example/ping")
        .first()
    )
    assert event is not None
    assert event.method == "GET"
    assert event.actor_user_id is None
    assert event.outcome == "success"
    assert event.action_label == "健康检查"


def test_create_request_audit_captures_created_resource_target(
    test_client,
    test_db_session: Session,
    init_test_database,
):
    headers = _login_admin(test_client)

    task_resp = test_client.post(
        "/api/example/tasks",
        json={"name": "audited_target_task"},
        headers=headers,
    )
    assert task_resp.status_code == HTTPStatus.ACCEPTED, task_resp.text
    task_id = task_resp.json()["id"]

    task_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.action == "example.task.create")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert task_event is not None
    assert task_event.resource_type == "example_async_task"
    assert task_event.resource_id == task_id
    assert task_event.target_summary == "audited_target_task"
    assert task_event.actor_username == "admin"
    assert task_event.action_label == "创建长时异步任务"

    item_resp = test_client.post(
        "/api/example/items",
        json={"name": "audited_target_item"},
        headers=headers,
    )
    assert item_resp.status_code == HTTPStatus.CREATED, item_resp.text

    item_event = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.action == "example.item.create")
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert item_event is not None
    assert item_event.resource_type == "item"
    assert item_event.resource_id == str(item_resp.json()["id"])
    assert item_event.target_summary == "audited_target_item"


def test_health_and_non_route_requests_are_not_audited(
    test_client,
    test_db_session: Session,
):
    test_client.get("/api/health")
    test_client.get("/api/nonexistent-route")
    test_client.get("/")

    assert test_db_session.query(AuditEvent).count() == 0


class _GitHubMockHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/login/oauth/access_token":
            self.send_error(404)
            return
        self._send_json({"access_token": "mock-github-token", "token_type": "bearer"})

    def do_GET(self) -> None:
        if self.path == "/user":
            self._send_json(
                {
                    "id": "fake-github-10001",
                    "login": "fake_github_user",
                    "name": "Mock GitHub User",
                    "avatar_url": "http://mock.local/github.png",
                }
            )
            return
        if self.path == "/user/emails":
            self._send_json(
                [
                    {
                        "email": "fake-github@example.com",
                        "primary": True,
                        "verified": True,
                    }
                ]
            )
            return
        self.send_error(404)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def mock_github_provider_server() -> Iterator[None]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _GitHubMockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server_host_port(server)
    update_provider_runtime_config(
        PROVIDER_GITHUB_OAUTH, {"base_url": f"http://{host}:{port}"}
    )
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        clear_provider_runtime_configs()


def test_explicit_request_event_suppresses_middleware_duplicate(
    test_client,
    test_db_session: Session,
    monkeypatch,
    mock_github_provider_server,
):
    monkeypatch.setattr(global_config.oauth, "enabled_providers", ["GITHUB"])

    state = core.create_oauth_state("/dashboard")
    callback_resp = test_client.get(
        "/api/oauth/github/callback",
        params={"code": "github-code", "state": state},
        follow_redirects=False,
    )
    assert callback_resp.status_code in (302, 307), callback_resp.text

    events = (
        test_db_session.query(AuditEvent)
        .filter(
            AuditEvent.action.in_(
                ["auth.oauth.login", "auth.user.create.via_oauth", "auth.oauth.account.link"]
            )
        )
        .all()
    )
    assert len(events) == 1
    assert events[0].method == "GET"
    assert events[0].resource_type == "user"
    assert events[0].action_label == "GitHub OAuth 回调"
