"""前端错误上报服务。"""

from .short_transactions import FrontendErrorRateLimiter, log_frontend_error_report

__all__ = ["FrontendErrorRateLimiter", "log_frontend_error_report"]
