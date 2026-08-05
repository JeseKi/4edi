# -*- coding: utf-8 -*-
"""示例模块的请求侧服务。

这些函数由 HTTP 请求的受控短事务调用。创建长时任务时，业务任务、初始
日志与持久化 job 必须在同一个短事务中写入；本模块不在这里等待任务执行。
"""

from __future__ import annotations

import secrets
import string

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.providers import get_example_external_api_provider
from src.server.task_runtime import TaskReference, TaskRuntime

from ..dao import ExampleAsyncTaskDAO, ExampleItemDAO
from ..models import ExampleAsyncTask, ExampleAsyncTaskLog, Item
from ..schemas import AsyncTaskCreate
from .long_tasks import EXAMPLE_ASYNC_TASK

ASYNC_TASK_ID_LENGTH = 32
ASYNC_TASK_ID_ALPHABET = string.ascii_letters + string.digits
MAX_TASK_ID_GENERATION_ATTEMPTS = 5


def create_item(db: Session, name: str) -> Item:
    dao = ExampleItemDAO(db)
    try:
        return dao.create(name)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="名称已存在"
        )


def get_item(db: Session, item_id: int) -> Item:
    dao = ExampleItemDAO(db)
    item = dao.get(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到")
    return item


async def fetch_external_status():
    return await get_example_external_api_provider().fetch_status()


def create_async_task(
    db: Session, payload: AsyncTaskCreate, requested_by_user_id: int | None
) -> ExampleAsyncTask:
    task_name = payload.name.strip()
    if not task_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="任务名称不能为空"
        )

    task_dao = ExampleAsyncTaskDAO(db)
    task = None
    for _ in range(MAX_TASK_ID_GENERATION_ATTEMPTS):
        task_id = _generate_async_task_id()
        if task_dao.get(task_id):
            continue

        task = task_dao.create(
            task_id=task_id,
            name=task_name,
            total_count=payload.total_count,
            fail_every=payload.fail_every,
            delay_ms=payload.delay_ms,
            requested_by_user_id=requested_by_user_id,
        )
        break

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务ID生成失败，请重试",
        )

    task_dao.append_log(
        task.id,
        level="info",
        message=f"任务已创建，总计 {payload.total_count} 项待处理。",
    )
    return task


def get_async_task_detail(
    db: Session, task_id: str
) -> tuple[ExampleAsyncTask, list[ExampleAsyncTaskLog]]:
    task_dao = ExampleAsyncTaskDAO(db)
    task = task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    logs = task_dao.list_logs(task_id)
    return task, logs


def launch_async_task(db: Session, runtime: TaskRuntime, task_id: str) -> str:
    """在创建任务的同一请求短事务内持久化入队记录。"""
    return runtime.enqueue(
        db,
        EXAMPLE_ASYNC_TASK,
        task_id,
        reference=TaskReference(resource_type="example_async_task", resource_id=task_id),
    )


def _generate_async_task_id() -> str:
    return "".join(
        secrets.choice(ASYNC_TASK_ID_ALPHABET)
        for _ in range(ASYNC_TASK_ID_LENGTH)
    )
