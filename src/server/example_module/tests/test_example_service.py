# -*- coding: utf-8 -*-
"""
示例模块服务层测试
"""

import re

import pytest
from sqlalchemy.orm import Session, sessionmaker
from fastapi import HTTPException

from src.server.example_module.models import Item
from src.server.example_module.schemas import AsyncTaskCreate
from src.server.example_module.service import (
    EXAMPLE_ASYNC_TASK,
    create_async_task,
    create_item,
    get_async_task_detail,
    get_item,
    launch_async_task,
    _run_async_task,
)
from src.server.auth.models import User
from src.server.audit.models import AuditEvent
from src.server.task_runtime import TaskContext, TaskRuntime
from src.server.task_runtime.models import BackgroundJob
from src.server.example_module.models import ExampleAsyncTask

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{32}$")


def _committing_session_runner(test_db_session: Session):
    factory = sessionmaker(
        bind=test_db_session.get_bind(), autocommit=False, autoflush=False
    )

    def run(operation):
        db = factory()
        try:
            result = operation(db)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return run


def test_create_item(test_db_session: Session):
    """测试创建项目"""
    # 正常创建
    item = create_item(test_db_session, "test_item")

    assert item is not None
    assert item.name == "test_item"

    # 测试重复名称
    with pytest.raises(HTTPException) as exc_info:
        create_item(test_db_session, "test_item")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "名称已存在"


def test_get_item(test_db_session: Session):
    """测试获取项目"""
    # 准备测试数据
    item = Item(name="test_item")
    test_db_session.add(item)
    test_db_session.commit()
    test_db_session.refresh(item)

    # 获取存在的项目
    retrieved_item = get_item(test_db_session, item.id)
    assert retrieved_item is not None
    assert retrieved_item.id == item.id
    assert retrieved_item.name == "test_item"

    # 获取不存在的项目
    with pytest.raises(HTTPException) as exc_info:
        get_item(test_db_session, 999999)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "未找到"


def test_async_task_service_flow(test_db_session: Session):
    user = User(
        username="task_runner",
        email="task_runner@example.com",
        name="Task Runner",
    )
    user.set_password("Password123")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)

    payload = AsyncTaskCreate(
        name="nightly batch",
        total_count=5,
        fail_every=2,
        delay_ms=0,
    )

    task = create_async_task(test_db_session, payload, user.id)
    assert TASK_ID_PATTERN.fullmatch(task.id)
    # 任务创建与入队在生产环境由路由的受控短事务统一提交；这里显式模拟该边界。
    test_db_session.commit()

    _run_async_task(
        TaskContext("test-job", 1, _committing_session_runner(test_db_session)),
        task.id,
    )

    detail, logs = get_async_task_detail(test_db_session, task.id)

    assert detail.status == "completed"
    assert detail.total_count == 5
    assert detail.processed_count == 5
    assert detail.success_count == 3
    assert detail.failure_count == 2
    assert detail.progress_percent == 100
    assert detail.started_at is not None
    assert detail.finished_at is not None
    assert len(logs) == 8
    assert logs[0].message == "任务已创建，总计 5 项待处理。"
    assert logs[-1].message == "任务执行完成，成功 3 项，失败 2 项。"

    audit_events = (
        test_db_session.query(AuditEvent)
        .filter(AuditEvent.resource_type == "example_async_task")
        .order_by(AuditEvent.id.asc())
        .all()
    )
    assert [event.action for event in audit_events] == [
        "example.task.started",
        "example.task.completed",
    ]
    assert audit_events[-1].resource_id == task.id
    assert audit_events[-1].actor_user_id == user.id


def test_get_async_task_detail_raises_when_missing(test_db_session: Session):
    with pytest.raises(HTTPException) as exc_info:
        get_async_task_detail(test_db_session, "A" * 32)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "任务不存在"


def test_async_task_and_persistent_job_roll_back_together(test_db_session: Session):
    """发布端必须把业务任务、初始日志和 job 放进同一个短事务。"""
    runtime = TaskRuntime(definitions=(EXAMPLE_ASYNC_TASK,))
    payload = AsyncTaskCreate(
        name="atomic publish",
        total_count=1,
        fail_every=0,
        delay_ms=0,
    )

    def create_then_fail(db: Session) -> None:
        task = create_async_task(db, payload, requested_by_user_id=None)
        launch_async_task(db, runtime, task.id)
        raise RuntimeError("simulate request failure")

    with pytest.raises(RuntimeError, match="simulate request failure"):
        _committing_session_runner(test_db_session)(create_then_fail)

    assert test_db_session.query(ExampleAsyncTask).count() == 0
    assert test_db_session.query(BackgroundJob).count() == 0
