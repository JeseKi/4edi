# -*- coding: utf-8 -*-
"""Request audit middleware for legitimate API requests."""

from __future__ import annotations

from time import perf_counter

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.server.database_executor import get_database_executor

from . import service
from .service import AuditContext

AUDITED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})
EXCLUDED_PATHS = frozenset({"/api/health", "/api/frontend-config"})


class AuditMiddleware(BaseHTTPMiddleware):
    """Persist a sanitized audit event for each legitimate API request."""

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() not in AUDITED_METHODS:
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api") or path in EXCLUDED_PATHS:
            return await call_next(request)

        started_at = perf_counter()
        response: Response | None = None
        raised: BaseException | None = None

        try:
            response = await call_next(request)
            return response
        except BaseException as exc:
            raised = exc
            raise
        finally:
            duration_ms = int((perf_counter() - started_at) * 1000)
            status_code = response.status_code if response is not None else 500
            outcome = "success" if raised is None and status_code < 400 else "failure"
            try:
                await _record_request_audit(
                    request, outcome, status_code, duration_ms, raised
                )
            except Exception:
                logger.bind(
                    log_type="app",
                    request_id=getattr(request.state, "request_id", "-"),
                    client_ip=_client_ip(request),
                    user_id=getattr(request.state, "user_id", "-"),
                ).exception("写入审计日志失败")


async def _record_request_audit(
    request: Request,
    outcome: str,
    status_code: int,
    duration_ms: int,
    raised: BaseException | None,
) -> None:
    if not _matched_api_route(request):
        return
    if getattr(request.state, "audit_recorded", False):
        return
    event = _build_request_event(request, outcome, status_code, duration_ms, raised)
    if event["priority"] == "high":
        await _write_event(event, request)
        return
    app_runtime = request.app.state.runtime
    runtime = app_runtime.audit_runtime
    if runtime is None:
        await _write_event(event, request)
    else:
        runtime.enqueue(event)


def _matched_api_route(request: Request) -> bool:
    """True if the request matched a real API route (set by FastAPI after routing)."""
    route = request.scope.get("route")
    path_template = getattr(route, "path", None) if route is not None else None
    return bool(path_template and path_template.startswith("/api"))


def _build_request_event(
    request: Request,
    outcome: str,
    status_code: int,
    duration_ms: int,
    raised: BaseException | None,
) -> dict:
    context = _resolve_audit_context(request)
    route = request.scope.get("route")
    path_template = getattr(route, "path", None)
    action = context.action or _default_action(request.method, path_template or request.url.path)
    detail = {"query": dict(request.query_params), **context.detail}
    if raised is not None:
        detail["error_type"] = raised.__class__.__name__
        detail["error"] = str(raised)
    inferred_type, inferred_id = _infer_target(path_template, request.path_params)
    return {
        "outcome": outcome,
        "priority": service.resolve_priority(context.priority, action),
        "action": action,
        "action_label": getattr(route, "summary", None),
        "method": request.method,
        "path": request.url.path,
        "path_template": path_template,
        "http_status_code": status_code,
        "actor_user_id": getattr(request.state, "user_id", None),
        "actor_username": getattr(request.state, "username", None),
        "actor_role": getattr(request.state, "user_role", None),
        "actor_identifier": context.actor_identifier
        or getattr(request.state, "actor_identifier", None),
        "resource_type": context.resource_type or inferred_type,
        "resource_id": context.resource_id or inferred_id,
        "target_summary": context.target_summary,
        "request_id": getattr(request.state, "request_id", None),
        "client_ip": _client_ip(request),
        "user_agent": request.headers.get("user-agent"),
        "duration_ms": duration_ms,
        "detail": detail,
    }


async def _write_event(event: dict, request: Request) -> None:
    database_executor = get_database_executor(request)

    def _create(db) -> None:
        service.create_event(db, **event)

    await database_executor.run(_create)


def _resolve_audit_context(request: Request) -> AuditContext:
    value = getattr(request.state, "audit_context", None)
    if isinstance(value, AuditContext):
        return value
    if isinstance(value, dict):
        return AuditContext(**value)
    return AuditContext()


def _default_action(method: str, path: str) -> str:
    normalized = path.strip("/") or "root"
    normalized = normalized.replace("/", ".").replace("{", "").replace("}", "")
    return f"http.{method.lower()}.{normalized}"


def _infer_target(
    path_template: str | None,
    path_params: dict[str, object] | None,
) -> tuple[str | None, str | None]:
    """Infer resource type and id from the route template and path params."""
    if not path_template:
        return None, None
    segments = [
        part
        for part in path_template.strip("/").split("/")
        if part and part != "api"
    ]
    static_segments = [part for part in segments if not part.startswith("{")]
    param_segments = [part for part in segments if part.startswith("{")]
    resource_type = static_segments[-1] if static_segments else None
    resource_id = None
    if path_params and param_segments:
        values = [
            str(path_params[part.strip("{}")])
            for part in param_segments
            if path_params.get(part.strip("{}")) is not None
        ]
        resource_id = "/".join(values) if values else None
    return resource_type, resource_id


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else None
