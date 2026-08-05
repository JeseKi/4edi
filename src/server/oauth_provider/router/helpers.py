# -*- coding: utf-8 -*-
"""OAuth Provider 路由共享辅助函数。"""

import base64
from urllib.parse import parse_qs

from fastapi import HTTPException, Request, status


def client_audit_snapshot(client: dict) -> dict:
    return {
        key: client[key]
        for key in ("client_id", "name", "redirect_uris", "allowed_scopes", "is_active", "require_pkce")
        if key in client
    }


def client_changes(before: dict, after: dict) -> dict:
    before_snapshot = client_audit_snapshot(before)
    after_snapshot = client_audit_snapshot(after)
    changed_fields = [key for key, value in after_snapshot.items() if before_snapshot.get(key) != value]
    return {
        "changed_fields": changed_fields,
        "before": {key: before_snapshot[key] for key in changed_fields},
        "after": {key: after_snapshot[key] for key in changed_fields},
    }


async def read_urlencoded_form(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}


def required(form: dict[str, str], key: str) -> str:
    value = form.get(key)
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"缺少参数: {key}")
    return value


def resolve_client_credentials(request: Request, form: dict[str, str]) -> tuple[str, str | None]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth_header.split(" ", maxsplit=1)[1]).decode("utf-8")
            client_id, client_secret = decoded.split(":", maxsplit=1)
            return client_id, client_secret
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_client")
    return required(form, "client_id"), form.get("client_secret")
