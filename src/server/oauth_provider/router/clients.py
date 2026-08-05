# -*- coding: utf-8 -*-
"""OAuth Client 管理路由。"""

from fastapi import Depends, Request, status

from src.server.audit import service as audit_service
from src.server.auth.dependencies import AuthenticatedPrincipal, get_current_admin_writer
from src.server.database_executor import DatabaseExecutor, get_database_executor

from .. import service
from ..schemas import OAuthClientCreate, OAuthClientOut, OAuthClientSecretOut, OAuthClientUpdate
from . import router
from .helpers import client_audit_snapshot, client_changes


@router.get("/clients", response_model=list[OAuthClientOut], summary="列出 OAuth Clients")
async def list_clients(
    _: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: [OAuthClientOut.model_validate(item) for item in service.list_clients(db)]
    )


@router.post("/clients", response_model=OAuthClientSecretOut, status_code=status.HTTP_201_CREATED, summary="创建 OAuth Client")
async def create_client(
    request: Request, payload: OAuthClientCreate,
    _: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="admin.oauth_client.create", resource_type="oauth_client",
        target_summary=f"OAuth Client {payload.name.strip()}",
    )
    client = await database_executor.run(lambda db: service.create_client(
        db, name=payload.name, redirect_uris=payload.redirect_uris,
        allowed_scopes=payload.allowed_scopes, is_active=payload.is_active, require_pkce=payload.require_pkce,
    ))
    audit_service.attach_audit_context(
        request.state, resource_id=client["client_id"],
        target_summary=f"OAuth Client {client['name']} ({client['client_id']})",
        detail={"created": client_audit_snapshot(client)},
    )
    return OAuthClientSecretOut.model_validate(client)


@router.patch("/clients/{client_id}", response_model=OAuthClientOut, summary="更新 OAuth Client")
async def update_client(
    request: Request, client_id: str, payload: OAuthClientUpdate,
    _: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="admin.oauth_client.update", resource_type="oauth_client",
        resource_id=client_id, target_summary=f"OAuth Client {client_id}",
    )
    def _update(db) -> tuple[dict, dict]:
        before = service.get_client(db, client_id)
        client = service.update_client(db, client_id, payload.model_dump(exclude_unset=True))
        return client, before

    client, before = await database_executor.run(_update)
    audit_service.attach_audit_context(
        request.state, target_summary=f"OAuth Client {client['name']} ({client_id})",
        detail=client_changes(before, client),
    )
    return OAuthClientOut.model_validate(client)


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除 OAuth Client")
async def delete_client(
    request: Request, client_id: str,
    _: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="admin.oauth_client.delete", resource_type="oauth_client",
        resource_id=client_id, target_summary=f"OAuth Client {client_id}",
    )
    def _delete(db) -> dict:
        client = service.get_client(db, client_id)
        service.delete_client(db, client_id)
        return client

    client = await database_executor.run(_delete)
    audit_service.attach_audit_context(
        request.state, target_summary=f"OAuth Client {client['name']} ({client_id})",
        detail={"deleted": client_audit_snapshot(client)},
    )


@router.post("/clients/{client_id}/secret", response_model=OAuthClientSecretOut, summary="重置 OAuth Client Secret")
async def reset_client_secret(
    request: Request, client_id: str,
    _: AuthenticatedPrincipal = Depends(get_current_admin_writer),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    audit_service.attach_audit_context(
        request.state, action="admin.oauth_client.secret.rotate", resource_type="oauth_client",
        resource_id=client_id, target_summary=f"OAuth Client {client_id}",
    )
    client = await database_executor.run(
        lambda db: service.reset_client_secret(db, client_id)
    )
    audit_service.attach_audit_context(
        request.state, target_summary=f"OAuth Client {client['name']} ({client_id})",
        detail={"secret_rotated": True},
    )
    return OAuthClientSecretOut.model_validate(client)
