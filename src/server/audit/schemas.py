# -*- coding: utf-8 -*-
"""Audit event API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AuditOutcome = Literal["success", "failure"]
AuditPriority = Literal["high", "low"]


class AuditEventOut(BaseModel):
    id: int
    created_at: datetime
    outcome: AuditOutcome
    priority: AuditPriority
    action: str
    action_label: str | None = None
    method: str | None
    path: str | None
    path_template: str | None
    http_status_code: int | None
    actor_user_id: int | None
    actor_username: str | None
    actor_role: str | None
    actor_identifier: str | None
    resource_type: str | None
    resource_id: str | None
    target_summary: str | None
    request_id: str | None
    client_ip: str | None
    user_agent: str | None
    duration_ms: int | None
    detail: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("detail", mode="before")
    @classmethod
    def normalize_detail(cls, value: object) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}


class AuditEventListOut(BaseModel):
    items: list[AuditEventOut]
    total: int
    page: int
    page_size: int
