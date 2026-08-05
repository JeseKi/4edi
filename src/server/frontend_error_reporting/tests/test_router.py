from __future__ import annotations

import json

from src.server.config import global_config
from src.server.frontend_error_reporting.router import _rate_limiter
from src.server.frontend_error_reporting.schemas import FrontendErrorReport
from src.server.frontend_error_reporting.service import short_transactions


def _payload() -> dict:
    return {
        "timestamp": "2026-07-19T08:00:00.000Z",
        "transport": "axios",
        "method": "POST",
        "url": "http://testserver/api/example",
        "curl": "curl --request POST --url 'http://testserver/api/example'",
        "request_headers": {"Authorization": "[REDACTED]"},
        "response": {
            "status": 500,
            "status_text": "Internal Server Error",
            "headers": {"content-type": "application/json"},
            "body": '{"detail":"failed"}',
            "body_truncated": False,
            "body_is_binary": False,
        },
        "error": "Request failed with status code 500",
    }


def test_frontend_error_report_is_accepted_and_logged(test_client, monkeypatch) -> None:
    messages: list[str] = []
    bindings: list[dict] = []

    class BoundLogger:
        def error(self, message: str) -> None:
            messages.append(message)

    class FakeLogger:
        def bind(self, **kwargs):
            bindings.append(kwargs)
            return BoundLogger()

    monkeypatch.setattr(short_transactions, "logger", FakeLogger())
    _rate_limiter.clear()

    response = test_client.post(
        "/api/frontend-errors",
        json=_payload(),
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 204
    assert bindings == [{"log_type": "frontend", "client_ip": "127.0.0.1"}]
    assert json.loads(messages[0])["curl"] == _payload()["curl"]
    assert json.loads(messages[0])["response"]["status"] == 500


def test_frontend_error_report_rejects_untrusted_origin(test_client) -> None:
    _rate_limiter.clear()
    response = test_client.post(
        "/api/frontend-errors",
        json=_payload(),
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403


def test_frontend_error_report_accepts_api_same_origin(test_client) -> None:
    _rate_limiter.clear()
    response = test_client.post(
        "/api/frontend-errors",
        json=_payload(),
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 204


def test_frontend_error_report_enforces_size_and_rate_limit(test_client, monkeypatch) -> None:
    _rate_limiter.clear()
    monkeypatch.setattr(global_config.frontend_error_reporting, "rate_limit_per_minute", 1)

    headers = {"Origin": "http://localhost:3000"}
    assert test_client.post("/api/frontend-errors", json=_payload(), headers=headers).status_code == 204
    assert test_client.post("/api/frontend-errors", json=_payload(), headers=headers).status_code == 429

    _rate_limiter.clear()
    oversized = json.dumps(
        {"padding": "x" * (global_config.frontend_error_reporting.max_payload_bytes + 1)}
    )
    response = test_client.post(
        "/api/frontend-errors",
        content=oversized,
        headers={**headers, "Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_frontend_report_schema_serializes_response_body() -> None:
    report = FrontendErrorReport.model_validate(_payload())
    assert report.model_dump(mode="json")["response"]["body"] == '{"detail":"failed"}'
