"""接收浏览器 HTTP 错误报告的公开接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import ValidationError

from src.server.config import global_config
from src.server.audit import service as audit_service
from src.server.frontend_error_reporting.schemas import FrontendErrorReport
from src.server.frontend_error_reporting.service import (
    FrontendErrorRateLimiter,
    log_frontend_error_report,
)

router = APIRouter(prefix="/api", tags=["前端错误日志"])
_rate_limiter = FrontendErrorRateLimiter()


def _origin_is_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return False

    allowed_origins = set(global_config.app.allowed_origins)
    own_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
    if origin == own_origin:
        return True
    if origin in allowed_origins and origin != "*":
        return True

    # `*` 不能作为匿名日志入口的信任边界；上面的自身同源分支仍可正常使用。
    return False


@router.post(
    "/frontend-errors",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="上报前端请求错误",
)
async def report_frontend_error(request: Request) -> Response:
    """校验、限流并写入前端请求失败日志，不进行任何数据库持久化。"""

    if not _origin_is_allowed(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不允许的来源")

    content_length = request.headers.get("content-length")
    max_payload_bytes = global_config.frontend_error_reporting.max_payload_bytes
    if content_length and content_length.isdigit() and int(content_length) > max_payload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    body = await request.body()
    if len(body) > max_payload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    client_ip = request.client.host if request.client else "-"
    if not _rate_limiter.allow(
        client_ip,
        limit=global_config.frontend_error_reporting.rate_limit_per_minute,
    ):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS)

    try:
        report = FrontendErrorReport.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc

    audit_service.attach_audit_context(
        request.state,
        action="frontend_error.report",
        resource_type="frontend_error",
        target_summary=f"{report.method} {report.url}",
        detail={
            "url": report.url,
            "method": report.method,
            "transport": report.transport,
            "error_code": report.error_code,
            "page_url": report.page_url,
        },
    )
    log_frontend_error_report(report, client_ip=client_ip)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
