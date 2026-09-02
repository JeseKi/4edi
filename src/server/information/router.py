# -*- coding: utf-8 -*-
"""信息发布路由：公开浏览、登录发布、管理员审核三组接口。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, status
from sqlalchemy.orm import Session

from src.server.auth.dependencies.admin import get_current_admin
from src.server.auth.dependencies.current_user import (
    AuthenticatedPrincipal,
    get_current_principal,
)
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.database_executor import DatabaseExecutor, get_database_executor

from . import service
from .models import InformationStatus
from .models import PublisherVerificationStatus
from .schemas import (
    CategoryOut,
    ContactOut,
    PageOut,
    PostAdminListOut,
    PostCreateIn,
    PostDetailOut,
    PostMineOut,
    PostOut,
    PostReviewIn,
    PublisherVerificationCreateIn,
    PublisherVerificationOut,
    PublisherVerificationPageOut,
    PublisherVerificationReviewIn,
)

router = APIRouter(prefix="/api/information", tags=["商城-信息发布"])
admin_router = APIRouter(prefix="/api/information/admin", tags=["商城-信息发布-管理员"])

_SCOPE = [SCOPE_PROFILE_READ]

_SORT_LITERAL = Literal["latest", "hot", "recommended"]
_STATUS_LITERAL = Literal["pending", "approved", "rejected"]


def _require_login(
    current_user: AuthenticatedPrincipal = Security(
        get_current_principal, scopes=_SCOPE
    ),
) -> AuthenticatedPrincipal:
    return current_user


# ---------------------------------------------------------------------------
# 公开：分类 / 列表 / 详情
# ---------------------------------------------------------------------------


@router.get("/categories", summary="信息分类", response_model=list[CategoryOut])
async def list_categories() -> list[dict]:
    """返回分类列表及各分类的发布/详情属性字段定义。"""
    return service.list_categories()


@router.get("", summary="信息列表", response_model=PageOut[PostOut])
async def list_information(
    category: str | None = Query(default=None, max_length=32, description="分类 key"),
    keyword: str | None = Query(default=None, max_length=100, description="搜索关键词"),
    sort: _SORT_LITERAL = Query(default="latest", description="排序：最新/最热/推荐"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db: Session) -> dict:
        items, total = service.list_public(
            db,
            category=category,
            keyword=keyword,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    return await database_executor.run(_list)


@router.get("/mine", summary="我的发布", response_model=list[PostMineOut])
async def list_my_information(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: service.list_mine(db, current_user.user_id)
    )


@router.get(
    "/verification/me",
    summary="我的发布者实名记录",
    response_model=list[PublisherVerificationOut],
)
async def my_publisher_verifications(
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    return await database_executor.run(
        lambda db: service.list_my_verifications(db, current_user.user_id)
    )


@router.post(
    "/verification",
    summary="提交发布者实名申请",
    response_model=PublisherVerificationOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_publisher_verification(
    request: Request,
    payload: PublisherVerificationCreateIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _submit(db):
        verification = service.submit_verification(
            db, current_user.user_id, payload.model_dump()
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="information.publisher_verification.submit",
            resource_type="publisher_verification",
            resource_id=verification.id,
            target_summary=f"发布者实名申请 {verification.id}",
        )
        return service.get_verification_payload(db, verification.id)

    return await database_executor.run(_submit)


@router.get("/{post_id}", summary="信息详情", response_model=PostDetailOut)
async def get_information(
    post_id: int,
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db: Session) -> dict:
        detail = service.get_public_detail(db, post_id)
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="信息不存在或未公开"
            )
        return detail

    return await database_executor.run(_get)


@router.get(
    "/{post_id}/contact",
    summary="查看已公开信息的完整联系方式",
    response_model=ContactOut,
)
async def get_information_contact(
    request: Request,
    post_id: int,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _get(db: Session) -> dict:
        contact = service.get_contact(db, post_id)
        if contact is None:
            raise HTTPException(status_code=404, detail="信息不存在或未公开")
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="information.contact.read",
            resource_type="information",
            resource_id=post_id,
            target_summary=f"查看信息 {post_id} 联系方式",
            detail={"viewer_user_id": current_user.user_id},
        )
        return contact

    return await database_executor.run(_get)


# ---------------------------------------------------------------------------
# 登录：发布 / 删除
# ---------------------------------------------------------------------------


@router.post(
    "",
    summary="发布信息",
    response_model=PostMineOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_information(
    payload: PostCreateIn,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _create(db: Session) -> dict:
        post = service.create_post(db, current_user.user_id, payload.model_dump())
        return service.mine_payload(post, current_user.username)

    return await database_executor.run(_create)


@router.delete(
    "/{post_id}",
    summary="删除自己发布的信息",
    response_model=dict,
)
async def delete_information(
    post_id: int,
    current_user: AuthenticatedPrincipal = Depends(_require_login),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _delete(db: Session) -> dict:
        service.delete_post(db, current_user.user_id, post_id)
        return {"deleted": True}

    return await database_executor.run(_delete)


# ---------------------------------------------------------------------------
# 管理员：列表 / 审核 / 置顶
# ---------------------------------------------------------------------------


@admin_router.get("/posts", summary="信息审核列表", response_model=PageOut[PostAdminListOut])
async def admin_list_information(
    post_status: _STATUS_LITERAL | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db: Session) -> dict:
        status_filter = InformationStatus(post_status) if post_status else None
        items, total = service.admin_list(
            db,
            post_status=status_filter,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    return await database_executor.run(_list)


@admin_router.post(
    "/posts/{post_id}/review",
    summary="审核信息",
    response_model=PostAdminListOut,
)
async def admin_review_information(
    request: Request,
    post_id: int,
    payload: PostReviewIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _review(db: Session) -> dict:
        post = service.admin_review(
            db,
            post_id,
            approved=payload.approved,
            reject_reason=payload.reject_reason,
            reviewer_user_id=current_admin.user_id,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="information.post.review",
            resource_type="information",
            resource_id=post.id,
            target_summary=post.title,
        )
        return service.get_admin_item_payload(db, post)

    return await database_executor.run(_review)


@admin_router.get(
    "/verifications",
    summary="发布者实名审核列表",
    response_model=PublisherVerificationPageOut,
)
async def admin_list_publisher_verifications(
    verification_status: _STATUS_LITERAL | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _list(db: Session) -> dict:
        status_filter = (
            PublisherVerificationStatus(verification_status)
            if verification_status
            else None
        )
        items, total = service.admin_list_verifications(
            db,
            verification_status=status_filter,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    return await database_executor.run(_list)


@admin_router.post(
    "/verifications/{verification_id}/review",
    summary="审核发布者实名申请",
    response_model=PublisherVerificationOut,
)
async def admin_review_publisher_verification(
    request: Request,
    verification_id: int,
    payload: PublisherVerificationReviewIn,
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _review(db: Session) -> dict:
        verification = service.review_verification(
            db,
            verification_id,
            approved=payload.approved,
            reject_reason=payload.reject_reason,
            reviewer_user_id=current_admin.user_id,
        )
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            priority="high",
            action="information.publisher_verification.review",
            resource_type="publisher_verification",
            resource_id=verification.id,
            target_summary=f"发布者实名申请 {verification.id}",
            detail={"approved": payload.approved},
        )
        return service.get_verification_payload(db, verification.id)

    return await database_executor.run(_review)


@admin_router.post(
    "/posts/{post_id}/top",
    summary="置顶/取消置顶信息",
    response_model=PostAdminListOut,
)
async def admin_toggle_information_top(
    request: Request,
    post_id: int,
    on: bool = Query(...),
    current_admin: AuthenticatedPrincipal = Security(get_current_admin),
    database_executor: DatabaseExecutor = Depends(get_database_executor),
):
    def _toggle(db: Session) -> dict:
        post = service.admin_toggle_top(db, post_id, on=on)
        from src.server.audit import service as audit_service

        audit_service.attach_audit_context(
            request.state,
            action="information.post.top",
            resource_type="information",
            resource_id=post.id,
            target_summary=post.title,
        )
        return service.get_admin_item_payload(db, post)

    return await database_executor.run(_toggle)
