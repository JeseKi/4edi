# -*- coding: utf-8 -*-
"""Audit event service."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .dao import AuditEventDAO
from .models import AuditEvent
from .schemas import AuditEventOut

SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "token",
    "secret",
    "code",
    "authorization",
    "cookie",
    "credential",
)


@dataclass
class AuditContext:
    priority: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | int | None = None
    target_summary: str | None = None
    actor_identifier: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


def attach_audit_context(target: object, **fields: Any) -> None:
    current = getattr(target, "audit_context", None)
    if isinstance(current, AuditContext):
        context = current
    elif isinstance(current, dict):
        context = AuditContext(**current)
    else:
        context = AuditContext()

    for key, value in fields.items():
        if key == "detail" and isinstance(value, dict):
            context.detail.update(value)
            continue
        if hasattr(context, key):
            setattr(context, key, value)
    setattr(target, "audit_context", context)


def attach_user_audit_context(
    target: object,
    *,
    action: str,
    user: Any,
    detail: dict[str, Any] | None = None,
) -> None:
    """Attach a safe, consistent target summary for a user operation."""
    user_id = getattr(user, "id", getattr(user, "user_id", None))
    username = getattr(user, "username", None)
    summary = f"用户 {username} (ID {user_id})" if username and user_id else "用户"
    attach_audit_context(
        target,
        action=action,
        resource_type="user",
        resource_id=user_id,
        target_summary=summary,
        detail=detail or {},
    )


def mask_identifier(value: str | None) -> str | None:
    """Return a minimally useful masked identifier for audit records."""
    if not value:
        return None
    if "@" in value:
        local, domain = value.split("@", maxsplit=1)
        return f"{local[:1]}***@{domain}"
    return f"{value[:1]}***"


def create_request_event(
    db: Session,
    request: Request,
    *,
    outcome: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    target_summary: str | None = None,
    actor_identifier: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent | None:
    """Write an explicit event for a sensitive read or a write performed by GET."""
    request.state.audit_recorded = True
    route = request.scope.get("route")
    path_template = getattr(route, "path", None)
    action_label = getattr(route, "summary", None)
    forwarded_for = request.headers.get("x-forwarded-for")
    client_ip = (
        forwarded_for.split(",", maxsplit=1)[0].strip()
        if forwarded_for
        else (request.client.host if request.client else None)
    )
    try:
        return create_event(
            db,
            outcome=outcome,
            action=action,
            action_label=action_label,
            priority="high",
            method=request.method,
            path=request.url.path,
            path_template=path_template,
            http_status_code=200 if outcome == "success" else 500,
            actor_user_id=getattr(request.state, "user_id", None),
            actor_username=getattr(request.state, "username", None),
            actor_role=getattr(request.state, "user_role", None),
            actor_identifier=actor_identifier
            or getattr(request.state, "actor_identifier", None),
            resource_type=resource_type,
            resource_id=resource_id,
            target_summary=target_summary,
            request_id=getattr(request.state, "request_id", None),
            client_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            detail=detail,
        )
    except Exception:
        from loguru import logger

        logger.exception("写入高优先级审计日志失败")
        return None


def create_event(
    db: Session,
    *,
    outcome: str,
    action: str,
    action_label: str | None = None,
    priority: str | None = None,
    method: str | None = None,
    path: str | None = None,
    path_template: str | None = None,
    http_status_code: int | None = None,
    actor_user_id: int | None = None,
    actor_username: str | None = None,
    actor_role: str | None = None,
    actor_identifier: str | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    target_summary: str | None = None,
    request_id: str | None = None,
    client_ip: str | None = None,
    user_agent: str | None = None,
    duration_ms: int | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    event = build_event(
        outcome=outcome,
        action=action,
        action_label=action_label,
        priority=priority,
        method=method,
        path=path,
        path_template=path_template,
        http_status_code=http_status_code,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        actor_role=actor_role,
        actor_identifier=actor_identifier,
        resource_type=resource_type,
        resource_id=resource_id,
        target_summary=target_summary,
        request_id=request_id,
        client_ip=client_ip,
        user_agent=user_agent,
        duration_ms=duration_ms,
        detail=detail,
    )
    return AuditEventDAO(db).create(event)


def build_event(**fields: Any) -> AuditEvent:
    action = fields.get("action")
    event = AuditEvent(
        outcome=fields["outcome"],
        priority=resolve_priority(fields.get("priority"), action),
        action=_truncate(action, 120) or "unknown",
        action_label=_truncate(fields.get("action_label"), 120),
        method=_truncate(fields.get("method", "").upper(), 10) if fields.get("method") else None,
        path=_truncate(fields.get("path"), 500),
        path_template=_truncate(fields.get("path_template"), 500),
        http_status_code=fields.get("http_status_code"),
        actor_user_id=fields.get("actor_user_id"),
        actor_username=_truncate(fields.get("actor_username"), 80),
        actor_role=_truncate(fields.get("actor_role"), 40),
        actor_identifier=_truncate(fields.get("actor_identifier"), 255),
        resource_type=_truncate(fields.get("resource_type"), 80),
        resource_id=_truncate(str(fields["resource_id"]), 120) if fields.get("resource_id") is not None else None,
        target_summary=_truncate(fields.get("target_summary"), 500),
        request_id=_truncate(fields.get("request_id"), 64),
        client_ip=_truncate(fields.get("client_ip"), 80),
        user_agent=_truncate(fields.get("user_agent"), 500),
        duration_ms=fields.get("duration_ms"),
        detail_json=_dump_detail(fields.get("detail")),
    )
    return event


def resolve_priority(value: str | None, action: str | None) -> str:
    if value in {"high", "low"}:
        return value
    high_prefixes = (
        "admin.",
        "http.get.api.admin.",
        "auth.password",
        "auth.user.register",
        "auth.profile.update",
        "auth.profile.email.update",
        "auth.email_verification.request",
        "auth.oauth.",
        "oauth.authorization.",
        "oauth.device_",
        "oauth.token.",
    )
    return "high" if action and action.startswith(high_prefixes) else "low"


def list_events(
    db: Session,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    outcome: str | None = None,
    method: str | None = None,
    actor_user_id: int | None = None,
    resource_type: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> tuple[list[AuditEventOut], int]:
    items, total = AuditEventDAO(db).list_filtered(
        page=page,
        page_size=page_size,
        q=q.strip() if q and q.strip() else None,
        outcome=outcome,
        method=method,
        actor_user_id=actor_user_id,
        resource_type=resource_type.strip() if resource_type else None,
        created_from=created_from,
        created_to=created_to,
    )
    return [to_out(item) for item in items], total


def to_out(event: AuditEvent) -> AuditEventOut:
    data = {
        **event.__dict__,
        "detail": _load_detail(event.detail_json),
    }
    return AuditEventOut.model_validate(data)


def sanitized_detail(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return _sanitize_value(value)


def _dump_detail(value: dict[str, Any] | None) -> str:
    safe_value = sanitized_detail(value)
    return json.dumps(safe_value, ensure_ascii=False, sort_keys=True, default=str)


def _load_detail(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                result[key_text] = "[REDACTED]"
            else:
                result[key_text] = _sanitize_value(item)
        return result
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]
