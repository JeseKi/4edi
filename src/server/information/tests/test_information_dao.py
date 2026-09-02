# -*- coding: utf-8 -*-
"""信息发布 DAO 层测试：创建、查询过滤、排序、分页。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.information.dao import InformationPostDAO
from src.server.information.models import (
    InformationPost,
    InformationStatus,
    PublisherVerification,
)
from src.server.information.tests._compliance_helpers import qualify_user_in_db


def _make_user(db: Session, username: str) -> User:
    user = User(username=username, email=f"{username}@example.com", name=username)
    user.set_password("Password123")
    db.add(user)
    db.flush()
    qualify_user_in_db(db, user)
    return user


def _make_post(
    db: Session,
    *,
    user_id: int,
    title: str = "示例信息",
    category: str = "mini_program",
    content: str = "详情内容" * 20,
    price: str | None = "面议",
    view_count: int = 0,
    is_top: bool = False,
    status: InformationStatus = InformationStatus.PENDING,
) -> InformationPost:
    dao = InformationPostDAO(db)
    verification = (
        db.query(PublisherVerification)
        .filter(PublisherVerification.user_id == user_id)
        .one()
    )
    post = dao.create(
        title=title,
        category=category,
        content=content,
        contact_name="张三",
        contact_phone="18312345067",
        poster_user_id=user_id,
        price=price,
        attributes={"dev_method": "原生开发"},
        publisher_verification_id=verification.id,
    )
    if status != InformationStatus.PENDING:
        dao.update_status(
            post,
            status=status,
            reject_reason=None if status == InformationStatus.APPROVED else "不符合规范",
            approved=status == InformationStatus.APPROVED,
            reviewer_user_id=user_id,
        )
    if view_count:
        post.view_count = view_count
    if is_top:
        post.is_top = True
    db.flush()
    return post


def test_info_dao_create(test_db_session: Session):
    user = _make_user(test_db_session, "creator-1")
    post = _make_post(test_db_session, user_id=user.id)

    assert post.id is not None
    assert post.status == InformationStatus.PENDING
    assert post.view_count == 0
    assert post.contact_name == "张三"
    assert post.poster_user_id == user.id

    dao = InformationPostDAO(test_db_session)
    found = dao.get(post.id)
    assert found is not None
    assert found.title == "示例信息"
    assert dao.get(999999) is None


def test_info_dao_list_public_filters_and_pagination(test_db_session: Session):
    user = _make_user(test_db_session, "creator-2")
    dao = InformationPostDAO(test_db_session)

    for i in range(5):
        _make_post(
            test_db_session,
            user_id=user.id,
            title=f"小程序-{i}",
            category="mini_program",
            view_count=i,
            status=InformationStatus.APPROVED,
        )
    _make_post(
        test_db_session,
        user_id=user.id,
        title="待审核-软件",
        category="software",
        status=InformationStatus.PENDING,
    )
    _make_post(
        test_db_session,
        user_id=user.id,
        title="置顶-网站",
        category="website",
        status=InformationStatus.APPROVED,
        is_top=True,
    )
    test_db_session.flush()

    # 只返回已通过
    items, total = dao.list_public(
        category=None, keyword=None, sort="latest", page=1, page_size=20
    )
    assert total == 6
    assert all(item.status == InformationStatus.APPROVED for item in items)

    # 分类过滤
    items, total = dao.list_public(
        category="mini_program", keyword=None, sort="latest", page=1, page_size=20
    )
    assert total == 5
    assert all(item.category == "mini_program" for item in items)

    # 关键词
    items, total = dao.list_public(
        category=None, keyword="置顶", sort="latest", page=1, page_size=20
    )
    assert total == 1
    assert items[0].title == "置顶-网站"

    # 推荐排序：置顶优先
    items, total = dao.list_public(
        category=None, keyword=None, sort="recommended", page=1, page_size=20
    )
    assert items[0].is_top is True

    # 最热排序：浏览量降序
    items, _ = dao.list_public(
        category="mini_program", keyword=None, sort="hot", page=1, page_size=20
    )
    view_counts = [item.view_count for item in items]
    assert view_counts == sorted(view_counts, reverse=True)

    # 分页
    items, total = dao.list_public(
        category=None, keyword=None, sort="latest", page=2, page_size=2
    )
    assert len(items) == 2
    assert total == 6


def test_info_dao_list_mine_and_admin_and_mutations(test_db_session: Session):
    alice = _make_user(test_db_session, "alice-info")
    bob = _make_user(test_db_session, "bob-info")
    dao = InformationPostDAO(test_db_session)

    alice_post = _make_post(test_db_session, user_id=alice.id, title="Alice 的信息")
    _make_post(test_db_session, user_id=bob.id, title="Bob 的信息")

    mine = dao.list_mine(alice.id)
    assert len(mine) == 1
    assert mine[0].title == "Alice 的信息"

    # 浏览量 +1
    dao.increment_view_count(alice_post)
    assert alice_post.view_count == 1

    # 审核状态流转
    dao.update_status(
        alice_post,
        status=InformationStatus.APPROVED,
        approved=True,
        reviewer_user_id=alice.id,
    )
    assert alice_post.status == InformationStatus.APPROVED
    assert alice_post.approved_at is not None
    assert alice_post.reject_reason is None

    dao.set_top(alice_post, on=True)
    assert alice_post.is_top is True

    items, total = dao.list_admin(status=InformationStatus.APPROVED, keyword=None, page=1, page_size=20)
    assert total == 1
    assert items[0].id == alice_post.id

    items, total = dao.list_admin(status=None, keyword="Bob", page=1, page_size=20)
    assert total == 1
    assert items[0].title == "Bob 的信息"
