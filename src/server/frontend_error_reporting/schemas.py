"""前端错误上报接口的数据结构。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FrontendResponseReport(BaseModel):
    """浏览器可读取到的失败响应摘要。"""

    model_config = ConfigDict(extra="forbid")

    status: int | None = Field(default=None, ge=0, le=999)
    status_text: str | None = Field(default=None, max_length=512)
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    body_truncated: bool = False
    body_is_binary: bool = False


class FrontendErrorReport(BaseModel):
    """由浏览器构造并提交的单次请求失败记录。"""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    transport: str = Field(pattern="^(axios|fetch|xhr)$")
    method: str = Field(min_length=1, max_length=16)
    url: str = Field(min_length=1, max_length=8192)
    curl: str = Field(min_length=1, max_length=32768)
    request_headers: dict[str, str] = Field(default_factory=dict)
    response: FrontendResponseReport | None = None
    error: str | None = Field(default=None, max_length=4096)
    error_code: str | None = Field(default=None, max_length=256)
    page_url: str | None = Field(default=None, max_length=8192)
    user_agent: str | None = Field(default=None, max_length=2048)
