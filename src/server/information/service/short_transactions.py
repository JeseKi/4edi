# -*- coding: utf-8 -*-
"""信息发布的请求侧短事务服务。

所有函数由 HTTP 请求的受控短事务调用；分类信息发布不涉及后台长时任务，
故本模块不依赖 task_runtime。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.auth.service import short_transactions as auth_transactions
from src.server.compliance import encrypt_sensitive_value
from src.server.compliance.config import compliance_config
from src.server.files.service import short_transactions as file_transactions

from ..constants import INFORMATION_CATEGORIES, category_name
from ..dao import InformationPostDAO
from ..models import (
    InformationPost,
    InformationStatus,
    PublisherVerification,
    PublisherVerificationStatus,
)

SORT_CHOICES = ("latest", "hot", "recommended")


def mask_phone(phone: str | None) -> str | None:
    """对手机号进行打码：保留前 3 位与后 4 位，中间以星号代替。

    位数不足 7 位时整体隐藏。
    """
    if not phone:
        return phone
    value = phone.strip()
    if len(value) < 7:
        return "*" * len(value)
    return f"{value[:3]}{'*' * 4}{value[-4:]}"


def _usernames(db: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.query(User.id, User.username).filter(User.id.in_(user_ids)).all()
    return {user_id: username for user_id, username in rows}


def _brief(post: InformationPost, username: str) -> dict:
    return {
        "id": post.id,
        "title": post.title,
        "category": post.category,
        "category_name": category_name(post.category),
        "price": post.price,
        "poster_username": username,
        "view_count": post.view_count,
        "is_top": post.is_top,
        "created_at": post.created_at,
    }


def _detail(post: InformationPost, username: str, *, phone_visible: bool) -> dict:
    data = _brief(post, username)
    data.update(
        {
            "content": post.content,
            "attributes": post.attributes or None,
            "contact_name": post.contact_name,
            "contact_phone": post.contact_phone if phone_visible else mask_phone(post.contact_phone),
            "approved_at": post.approved_at,
        }
    )
    return data


def mine_payload(post: InformationPost, username: str) -> dict:
    data = _detail(post, username, phone_visible=True)
    data.update(
        {
            "status": post.status.value,
            "reject_reason": post.reject_reason,
            "reviewed_by_user_id": post.reviewed_by_user_id,
            "reviewed_at": post.reviewed_at,
            "withdrawn_at": post.withdrawn_at,
            "withdrawn_reason": post.withdrawn_reason,
        }
    )
    return data


def admin_item_payload(
    post: InformationPost,
    username: str,
    verification: PublisherVerification | None = None,
) -> dict:
    data = mine_payload(post, username)
    data["poster_user_id"] = post.poster_user_id
    data.update(
        {
            "publisher_verification_id": post.publisher_verification_id,
            "publisher_real_name": getattr(verification, "real_name", None),
            "publisher_document_number_masked": getattr(
                verification, "document_number_masked", None
            ),
            "publisher_verification_valid": bool(
                verification and is_verification_currently_valid(verification)
            ),
        }
    )
    return data


def is_verification_currently_valid(verification: PublisherVerification) -> bool:
    return bool(
        verification.status == PublisherVerificationStatus.APPROVED
        and (
            verification.document_long_term
            or (
                verification.document_valid_until is not None
                and verification.document_valid_until >= date.today()
            )
        )
    )


def _current_verification(db: Session, user_id: int) -> PublisherVerification | None:
    rows = (
        db.query(PublisherVerification)
        .filter(
            PublisherVerification.user_id == user_id,
            PublisherVerification.status == PublisherVerificationStatus.APPROVED,
            or_(
                PublisherVerification.document_long_term.is_(True),
                PublisherVerification.document_valid_until >= date.today(),
            ),
        )
        .order_by(PublisherVerification.reviewed_at.desc(), PublisherVerification.id.desc())
        .all()
    )
    return rows[0] if rows else None


def list_categories() -> list[dict]:
    return [
        {
            "key": key,
            "name": info["name"],
            "attributes": info["attributes"],
        }
        for key, info in INFORMATION_CATEGORIES.items()
    ]


def create_post(db: Session, user_id: int, payload: dict) -> InformationPost:
    auth_transactions.assert_current_user_acceptances(db, user_id)
    verification = _current_verification(db, user_id)
    if verification is None:
        raise HTTPException(status_code=403, detail="请先完成并通过发布者实名认证")
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    category = payload.get("category") or ""
    contact_name = (payload.get("contact_name") or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标题不能为空")
    if category not in INFORMATION_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"未知信息分类：{category}")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="详情内容不能为空")
    if not contact_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="联系人不能为空")
    contact_phone = (payload.get("contact_phone") or "").strip()
    if not contact_phone:
        raise HTTPException(status_code=400, detail="联系电话不能为空")

    dao = InformationPostDAO(db)
    return dao.create(
        title=title,
        category=category,
        content=content,
        contact_name=contact_name,
        poster_user_id=user_id,
        price=(payload.get("price") or "").strip() or None,
        contact_phone=contact_phone,
        attributes=payload.get("attributes"),
        publisher_verification_id=verification.id,
    )


def list_public(
    db: Session,
    *,
    category: str | None,
    keyword: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    if sort not in SORT_CHOICES:
        sort = "latest"
    dao = InformationPostDAO(db)
    posts, total = dao.list_public(
        category=category, keyword=keyword, sort=sort, page=page, page_size=page_size
    )
    usernames = _usernames(db, {post.poster_user_id for post in posts})
    items = [_brief(post, usernames.get(post.poster_user_id, "用户")) for post in posts]
    return items, total


def get_public_detail(db: Session, post_id: int) -> dict | None:
    dao = InformationPostDAO(db)
    post = dao.get(post_id)
    if (
        post is None
        or post.status != InformationStatus.APPROVED
        or post.withdrawn_at is not None
        or post.publisher_verification_id is None
    ):
        return None
    verification = db.get(PublisherVerification, post.publisher_verification_id)
    if verification is None or not is_verification_currently_valid(verification):
        return None
    post = dao.increment_view_count(post)
    username = _usernames(db, {post.poster_user_id}).get(post.poster_user_id, "用户")
    return _detail(post, username, phone_visible=False)


def list_mine(db: Session, user_id: int) -> list[dict]:
    dao = InformationPostDAO(db)
    posts = dao.list_mine(user_id)
    username = _usernames(db, {user_id}).get(user_id, "用户")
    return [mine_payload(post, username) for post in posts]


def delete_post(db: Session, user_id: int, post_id: int) -> None:
    dao = InformationPostDAO(db)
    post = dao.get(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="信息不存在")
    if post.poster_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除他人发布的信息")
    if post.withdrawn_at is None:
        dao.withdraw(post, "发布者主动撤回")


def admin_list(
    db: Session,
    *,
    post_status: InformationStatus | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    dao = InformationPostDAO(db)
    posts, total = dao.list_admin(
        status=post_status, keyword=keyword, page=page, page_size=page_size
    )
    usernames = _usernames(db, {post.poster_user_id for post in posts})
    verification_ids = {
        post.publisher_verification_id for post in posts if post.publisher_verification_id
    }
    verifications = {
        item.id: item
        for item in db.query(PublisherVerification)
        .filter(PublisherVerification.id.in_(verification_ids))
        .all()
    } if verification_ids else {}
    items = []
    for post in posts:
        verification = (
            verifications.get(post.publisher_verification_id)
            if post.publisher_verification_id is not None
            else None
        )
        items.append(
            admin_item_payload(
                post, usernames.get(post.poster_user_id, "用户"), verification
            )
        )
    return items, total


def get_admin_item_payload(db: Session, post: InformationPost) -> dict:
    username = _usernames(db, {post.poster_user_id}).get(post.poster_user_id, "用户")
    verification = (
        db.get(PublisherVerification, post.publisher_verification_id)
        if post.publisher_verification_id is not None
        else None
    )
    return admin_item_payload(post, username, verification)


def admin_review(
    db: Session,
    post_id: int,
    *,
    approved: bool,
    reject_reason: str | None,
    reviewer_user_id: int,
) -> InformationPost:
    dao = InformationPostDAO(db)
    post = dao.get(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="信息不存在")
    if approved:
        if post.publisher_verification_id is None:
            raise HTTPException(status_code=400, detail="信息未关联发布者实名记录")
        verification = db.get(PublisherVerification, post.publisher_verification_id)
        if verification is None or not is_verification_currently_valid(verification):
            raise HTTPException(status_code=400, detail="发布者实名记录已失效，不能通过")
        return dao.update_status(
            post,
            status=InformationStatus.APPROVED,
            reject_reason=None,
            approved=True,
            reviewer_user_id=reviewer_user_id,
        )
    reason = (reject_reason or "").strip()
    if not reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="驳回时必须填写原因")
    return dao.update_status(
        post,
        status=InformationStatus.REJECTED,
        reject_reason=reason,
        approved=False,
        reviewer_user_id=reviewer_user_id,
    )


def admin_toggle_top(db: Session, post_id: int, *, on: bool) -> InformationPost:
    dao = InformationPostDAO(db)
    post = dao.get(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="信息不存在")
    return dao.set_top(post, on=on)


def get_contact(db: Session, post_id: int) -> dict | None:
    post = InformationPostDAO(db).get(post_id)
    if (
        post is None
        or post.status != InformationStatus.APPROVED
        or post.withdrawn_at is not None
        or post.publisher_verification_id is None
        or not post.contact_phone
    ):
        return None
    verification = db.get(PublisherVerification, post.publisher_verification_id)
    if verification is None or not is_verification_currently_valid(verification):
        return None
    return {"contact_name": post.contact_name, "contact_phone": post.contact_phone}


def _mask_document_number(value: str) -> str:
    normalized = "".join(value.strip().upper().split())
    if len(normalized) <= 7:
        return normalized[:1] + "*" * max(0, len(normalized) - 2) + normalized[-1:]
    return f"{normalized[:3]}{'*' * (len(normalized) - 7)}{normalized[-4:]}"


def verification_payload(
    verification: PublisherVerification,
    *,
    username: str,
    reviewer_username: str | None,
) -> dict:
    return {
        "id": verification.id,
        "user_id": verification.user_id,
        "username": username,
        "real_name": verification.real_name,
        "document_type": verification.document_type,
        "document_number_masked": verification.document_number_masked,
        "document_front_asset_id": verification.document_front_asset_id,
        "document_back_asset_id": verification.document_back_asset_id,
        "document_valid_until": verification.document_valid_until,
        "document_long_term": verification.document_long_term,
        "status": verification.status,
        "submitted_at": verification.submitted_at,
        "reviewer_user_id": verification.reviewer_user_id,
        "reviewer_username": reviewer_username,
        "reviewed_at": verification.reviewed_at,
        "reject_reason": verification.reject_reason,
        "is_currently_valid": is_verification_currently_valid(verification),
    }


def submit_verification(db: Session, user_id: int, payload: dict) -> PublisherVerification:
    auth_transactions.assert_current_user_acceptances(db, user_id)
    pending = (
        db.query(PublisherVerification.id)
        .filter(
            PublisherVerification.user_id == user_id,
            PublisherVerification.status == PublisherVerificationStatus.PENDING,
        )
        .first()
    )
    if pending is not None:
        raise HTTPException(status_code=409, detail="已有待审核的实名申请")
    document_type = payload["document_type"]
    back_asset_id = payload.get("document_back_asset_id")
    if document_type == "resident_identity_card" and not back_asset_id:
        raise HTTPException(status_code=422, detail="居民身份证必须上传正反面")
    long_term = bool(payload.get("document_long_term"))
    valid_until = payload.get("document_valid_until")
    if not long_term and valid_until is None:
        raise HTTPException(status_code=422, detail="请填写证件有效期或选择长期有效")
    if valid_until is not None and valid_until < date.today():
        raise HTTPException(status_code=422, detail="证件已过期")
    asset_ids = [payload["document_front_asset_id"]]
    if back_asset_id:
        asset_ids.append(back_asset_id)
    file_transactions.assert_owned_available_assets(
        db, owner_user_id=user_id, asset_ids=asset_ids, compliance_material=True
    )
    number = payload["document_number"].strip().upper()
    verification = PublisherVerification(
        user_id=user_id,
        real_name=payload["real_name"].strip(),
        document_type=document_type,
        document_number_encrypted=encrypt_sensitive_value(number),
        document_number_masked=_mask_document_number(number),
        document_front_asset_id=asset_ids[0],
        document_back_asset_id=back_asset_id,
        document_valid_until=None if long_term else valid_until,
        document_long_term=long_term,
        status=PublisherVerificationStatus.PENDING,
    )
    db.add(verification)
    db.flush()
    file_transactions.attach_asset_reference(
        db,
        asset_id=verification.document_front_asset_id,
        resource_type="publisher_verification",
        resource_id=verification.id,
        purpose="document_front",
    )
    if verification.document_back_asset_id:
        file_transactions.attach_asset_reference(
            db,
            asset_id=verification.document_back_asset_id,
            resource_type="publisher_verification",
            resource_id=verification.id,
            purpose="document_back",
        )
    return verification


def list_my_verifications(db: Session, user_id: int) -> list[dict]:
    rows = (
        db.query(PublisherVerification)
        .filter(PublisherVerification.user_id == user_id)
        .order_by(PublisherVerification.submitted_at.desc(), PublisherVerification.id.desc())
        .all()
    )
    username = _usernames(db, {user_id}).get(user_id, "用户")
    reviewer_ids = {row.reviewer_user_id for row in rows if row.reviewer_user_id}
    reviewers = _usernames(db, reviewer_ids)
    return [
        verification_payload(
            row,
            username=username,
            reviewer_username=(
                reviewers.get(row.reviewer_user_id)
                if row.reviewer_user_id is not None
                else None
            ),
        )
        for row in rows
    ]


def admin_list_verifications(
    db: Session,
    *,
    verification_status: PublisherVerificationStatus | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    query = db.query(PublisherVerification, User.username).join(
        User, User.id == PublisherVerification.user_id
    )
    if verification_status is not None:
        query = query.filter(PublisherVerification.status == verification_status)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(User.username.ilike(pattern), PublisherVerification.real_name.ilike(pattern))
        )
    total = query.count()
    rows = (
        query.order_by(PublisherVerification.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    reviewer_ids = {item.reviewer_user_id for item, _ in rows if item.reviewer_user_id}
    reviewers = _usernames(db, reviewer_ids)
    return [
        verification_payload(
            item,
            username=username,
            reviewer_username=(
                reviewers.get(item.reviewer_user_id)
                if item.reviewer_user_id is not None
                else None
            ),
        )
        for item, username in rows
    ], total


def get_verification_payload(db: Session, verification_id: int) -> dict:
    verification = db.get(PublisherVerification, verification_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="实名申请不存在")
    usernames = _usernames(
        db,
        {verification.user_id}
        | ({verification.reviewer_user_id} if verification.reviewer_user_id else set()),
    )
    return verification_payload(
        verification,
        username=usernames.get(verification.user_id, "用户"),
        reviewer_username=(
            usernames.get(verification.reviewer_user_id)
            if verification.reviewer_user_id is not None
            else None
        ),
    )


def get_verification_evidence(db: Session, verification_id: int) -> dict:
    """返回一条实名记录及所有绑定的信息发布记录，供监管取证页面使用。"""

    verification = db.get(PublisherVerification, verification_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="实名申请不存在")

    posts = (
        db.query(InformationPost)
        .filter(InformationPost.publisher_verification_id == verification_id)
        .order_by(InformationPost.created_at.desc(), InformationPost.id.desc())
        .all()
    )
    usernames = _usernames(
        db,
        {verification.user_id}
        | {post.poster_user_id for post in posts}
        | ({verification.reviewer_user_id} if verification.reviewer_user_id else set()),
    )
    verification_data = verification_payload(
        verification,
        username=usernames.get(verification.user_id, "用户"),
        reviewer_username=(
            usernames.get(verification.reviewer_user_id)
            if verification.reviewer_user_id is not None
            else None
        ),
    )
    post_data = [
        admin_item_payload(
            post,
            usernames.get(post.poster_user_id, "用户"),
            verification,
        )
        for post in posts
    ]
    return {"verification": verification_data, "posts": post_data}


def review_verification(
    db: Session,
    verification_id: int,
    *,
    approved: bool,
    reject_reason: str | None,
    reviewer_user_id: int,
) -> PublisherVerification:
    verification = db.get(PublisherVerification, verification_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="实名申请不存在")
    if verification.status != PublisherVerificationStatus.PENDING:
        raise HTTPException(status_code=400, detail="实名申请已审核")
    if approved:
        if not verification.document_long_term and (
            verification.document_valid_until is None
            or verification.document_valid_until < date.today()
        ):
            raise HTTPException(status_code=400, detail="证件已过期，不能通过")
        verification.status = PublisherVerificationStatus.APPROVED
        verification.reject_reason = None
    else:
        reason = (reject_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="驳回时必须填写原因")
        verification.status = PublisherVerificationStatus.REJECTED
        verification.reject_reason = reason
        file_transactions.release_asset_references(
            db,
            resource_type="publisher_verification",
            resource_id=verification.id,
            retain_until=datetime.now(timezone.utc)
            + timedelta(days=compliance_config.material_retention_days),
        )
    verification.reviewer_user_id = reviewer_user_id
    verification.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return verification
