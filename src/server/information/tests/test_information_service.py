# -*- coding: utf-8 -*-
"""信息发布服务层测试：创建、可见性、手机号打码、删除与审核。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.information import service
from src.server.information.dao import InformationPostDAO
from src.server.information.models import InformationStatus
from src.server.information.tests._compliance_helpers import qualify_user_in_db

VALID_PAYLOAD = {
    "category": "mini_program",
    "title": "小程序开发定制",
    "price": "电话咨询",
    "contact_name": "张三",
    "contact_phone": "18312345067",
    "content": "承接各类小程序开发与定制服务，支持电商、直播、预约等场景。",
    "attributes": {"dev_method": "原生开发", "secondary_dev": "是"},
}


def _make_user(db: Session, username: str) -> User:
    user = User(username=username, email=f"{username}@example.com", name=username)
    user.set_password("Password123")
    db.add(user)
    db.flush()
    qualify_user_in_db(db, user)
    return user


def _approve(db: Session, post_id: int) -> None:
    dao = InformationPostDAO(db)
    post = dao.get(post_id)
    assert post is not None
    dao.update_status(
        post,
        status=InformationStatus.APPROVED,
        approved=True,
        reviewer_user_id=post.poster_user_id,
    )
    db.flush()


def test_mask_phone():
    assert service.mask_phone(None) is None
    assert service.mask_phone("18312345067") == "183****5067"
    assert service.mask_phone("12345") == "*****"
    assert service.mask_phone("") == ""


def test_create_post_validations_and_flow(test_db_session: Session):
    user = _make_user(test_db_session, "svc-a")
    post = service.create_post(test_db_session, user.id, dict(VALID_PAYLOAD))

    assert post.status == InformationStatus.PENDING
    assert post.title == VALID_PAYLOAD["title"]
    assert post.contact_phone == "18312345067"
    assert post.attributes == {"dev_method": "原生开发", "secondary_dev": "是"}

    with pytest.raises(HTTPException) as exc_info:
        service.create_post(test_db_session, user.id, {**VALID_PAYLOAD, "category": "unknown"})
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        service.create_post(test_db_session, user.id, {**VALID_PAYLOAD, "title": "  "})
    assert exc_info.value.status_code == 400


def test_public_listing_only_approved_with_masked_phone(test_db_session: Session):
    user = _make_user(test_db_session, "svc-b")
    post = service.create_post(test_db_session, user.id, dict(VALID_PAYLOAD))
    _approve(test_db_session, post.id)

    # 新创建一条待审核，不应出现在公开列表
    service.create_post(
        test_db_session, user.id, {**VALID_PAYLOAD, "title": "待审核信息"}
    )
    test_db_session.flush()

    items, total = service.list_public(
        test_db_session, category=None, keyword=None, sort="latest", page=1, page_size=20
    )
    assert total == 1
    item = items[0]
    assert item["title"] == VALID_PAYLOAD["title"]
    assert "contact_phone" not in item

    detail = service.get_public_detail(test_db_session, post.id)
    assert detail is not None
    assert detail["contact_phone"] == "183****5067"
    assert detail["category_name"] == "小程序开发"
    assert detail["view_count"] == 1

    # 待审核信息对游客隐藏
    hidden = service.list_public(
        test_db_session, category=None, keyword="待审核", sort="latest", page=1, page_size=20
    )
    assert hidden[1] == 0
    assert service.get_public_detail(test_db_session, post.id + 1) is None


def test_mine_and_delete_permissions(test_db_session: Session):
    alice = _make_user(test_db_session, "svc-alice")
    bob = _make_user(test_db_session, "svc-bob")
    post = service.create_post(test_db_session, alice.id, dict(VALID_PAYLOAD))

    mine = service.list_mine(test_db_session, alice.id)
    assert len(mine) == 1
    assert mine[0]["contact_phone"] == "18312345067"  # 本人可见完整号码
    assert mine[0]["status"] == "pending"

    service.delete_post(test_db_session, alice.id, post.id)  # 本人可删除
    withdrawn = service.list_mine(test_db_session, alice.id)
    assert len(withdrawn) == 1
    assert withdrawn[0]["withdrawn_at"] is not None

    post2 = service.create_post(test_db_session, alice.id, dict(VALID_PAYLOAD))
    with pytest.raises(HTTPException) as exc_info:
        service.delete_post(test_db_session, bob.id, post2.id)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        service.delete_post(test_db_session, alice.id, 999999)
    assert exc_info.value.status_code == 404


def test_admin_review_and_toggle_top(test_db_session: Session):
    user = _make_user(test_db_session, "svc-admin-u")
    post = service.create_post(test_db_session, user.id, dict(VALID_PAYLOAD))

    # 驳回必须给原因
    with pytest.raises(HTTPException) as exc_info:
        service.admin_review(
            test_db_session,
            post.id,
            approved=False,
            reject_reason=None,
            reviewer_user_id=user.id,
        )
    assert exc_info.value.status_code == 400

    rejected = service.admin_review(
        test_db_session,
        post.id,
        approved=False,
        reject_reason="内容与类目不符",
        reviewer_user_id=user.id,
    )
    assert rejected.status == InformationStatus.REJECTED
    assert rejected.reject_reason == "内容与类目不符"

    approved = service.admin_review(
        test_db_session,
        post.id,
        approved=True,
        reject_reason=None,
        reviewer_user_id=user.id,
    )
    assert approved.status == InformationStatus.APPROVED
    assert approved.approved_at is not None
    assert approved.reject_reason is None

    toggled = service.admin_toggle_top(test_db_session, post.id, on=True)
    assert toggled.is_top is True

    items, total = service.admin_list(
        test_db_session,
        post_status=InformationStatus.APPROVED,
        keyword=None,
        page=1,
        page_size=20,
    )
    assert total == 1
    assert items[0]["is_top"] is True
    assert items[0]["poster_username"] == "svc-admin-u"
