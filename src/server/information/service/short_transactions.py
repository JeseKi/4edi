# -*- coding: utf-8 -*-
"""信息发布的请求侧短事务服务。

所有函数由 HTTP 请求的受控短事务调用；分类信息发布不涉及后台长时任务，
故本模块不依赖 task_runtime。
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..constants import INFORMATION_CATEGORIES, category_name
from ..dao import InformationPostDAO
from ..models import InformationPost, InformationStatus

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
        }
    )
    return data


def admin_item_payload(post: InformationPost, username: str) -> dict:
    data = mine_payload(post, username)
    data["poster_user_id"] = post.poster_user_id
    return data


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

    dao = InformationPostDAO(db)
    return dao.create(
        title=title,
        category=category,
        content=content,
        contact_name=contact_name,
        poster_user_id=user_id,
        price=(payload.get("price") or "").strip() or None,
        contact_phone=(payload.get("contact_phone") or "").strip() or None,
        attributes=payload.get("attributes"),
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
    if post is None or post.status != InformationStatus.APPROVED:
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
    db.delete(post)
    db.flush()


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
    items = [admin_item_payload(post, usernames.get(post.poster_user_id, "用户")) for post in posts]
    return items, total


def admin_review(
    db: Session, post_id: int, *, approved: bool, reject_reason: str | None
) -> InformationPost:
    dao = InformationPostDAO(db)
    post = dao.get(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="信息不存在")
    if approved:
        return dao.update_status(
            post,
            status=InformationStatus.APPROVED,
            reject_reason=None,
            approved=True,
        )
    reason = (reject_reason or "").strip()
    if not reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="驳回时必须填写原因")
    return dao.update_status(
        post, status=InformationStatus.REJECTED, reject_reason=reason, approved=False
    )


def admin_toggle_top(db: Session, post_id: int, *, on: bool) -> InformationPost:
    dao = InformationPostDAO(db)
    post = dao.get(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="信息不存在")
    return dao.set_top(post, on=on)
