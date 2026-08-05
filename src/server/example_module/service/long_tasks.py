# -*- coding: utf-8 -*-
"""示例模块的 worker 长时任务。

handler 不持有 Session 或 ORM 实体跨越等待、外部 I/O 或多个处理步骤。每个
数据库阶段均通过 ``TaskContext.run_db(...)`` 在独立短事务内完成，并只在
阶段之间保留不可变 DTO 或标量快照。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep

from sqlalchemy.orm import Session

from src.server.audit import service as audit_service
from src.server.auth.models import User
from src.server.task_runtime import TaskContext, TaskDefinition, TaskQueue

from ..dao import ExampleAsyncTaskDAO
from ..models import ExampleAsyncTask


@dataclass(frozen=True)
class _AsyncTaskInput:
    """后台任务在短事务外执行时所需的不可变输入。"""

    total_count: int
    fail_every: int
    delay_ms: int
    processed_count: int
    success_count: int
    failure_count: int


EXAMPLE_ASYNC_TASK = TaskDefinition(
    name="example.async_task.run",
    queue=TaskQueue.BATCH,
    handler=lambda context, task_id: _run_async_task(context, task_id),
    on_cancelled=lambda context, task_id: _mark_task_cancelled(context, task_id),
)


def _run_async_task(context: TaskContext, task_id: str) -> None:
    processed_count = 0
    success_count = 0
    failure_count = 0

    try:
        task_input = context.run_db(lambda db: _load_async_task_input(db, task_id))
        if task_input is None:
            return
        total_count = task_input.total_count
        fail_every = task_input.fail_every
        delay_ms = task_input.delay_ms
        processed_count = task_input.processed_count
        success_count = task_input.success_count
        failure_count = task_input.failure_count
        is_recovery = processed_count > 0

        def start(db: Session) -> None:
            dao = ExampleAsyncTaskDAO(db)
            status_message = "任务恢复执行" if is_recovery else "任务开始执行"
            log_message = (
                f"任务恢复执行，已处理 {processed_count} 项，预计处理 {total_count} 项数据。"
                if is_recovery
                else f"任务启动，预计处理 {total_count} 项数据。"
            )
            current = dao.update_status(
                task_id,
                status="running",
                last_message=status_message,
                started_at=datetime.now(timezone.utc),
            )
            _audit_task_event(
                db,
                current,
                action="example.task.started",
                outcome="success",
                detail={
                    "task_id": task_id,
                    "total_count": total_count,
                    "fail_every": fail_every,
                    "delay_ms": delay_ms,
                },
            )
            dao.append_log(task_id, level="info", message=log_message)

        context.run_db(start)

        for index in range(processed_count + 1, total_count + 1):
            if delay_ms > 0:
                sleep(delay_ms / 1000)

            if fail_every > 0 and index % fail_every == 0:
                failure_count += 1
                level = "warning"
                detail = f"第 {index} 项处理失败（模拟失败样本）"
            else:
                success_count += 1
                level = "info"
                detail = f"第 {index} 项处理成功"

            processed_count = success_count + failure_count

            def update(db: Session) -> None:
                dao = ExampleAsyncTaskDAO(db)
                dao.update_progress(
                    task_id,
                    processed_count=processed_count,
                    success_count=success_count,
                    failure_count=failure_count,
                    last_message=detail,
                )
                dao.append_log(task_id, level=level, message=detail)

            context.run_db(update)

        summary = f"任务执行完成，成功 {success_count} 项，失败 {failure_count} 项。"

        def complete(db: Session) -> None:
            dao = ExampleAsyncTaskDAO(db)
            current = dao.mark_completed(
                task_id,
                processed_count=processed_count,
                success_count=success_count,
                failure_count=failure_count,
                last_message=summary,
            )
            _audit_task_event(
                db,
                current,
                action="example.task.completed",
                outcome="success",
                detail={
                    "task_id": task_id,
                    "processed_count": processed_count,
                    "success_count": success_count,
                    "failure_count": failure_count,
                },
            )
            dao.append_log(task_id, level="info", message=summary)

        context.run_db(complete)
    except Exception as exc:
        error_message = f"任务执行异常：{exc}"

        def fail(db: Session) -> None:
            dao = ExampleAsyncTaskDAO(db)
            dao.mark_failed(
                task_id,
                processed_count=processed_count,
                success_count=success_count,
                failure_count=failure_count,
                last_message=error_message,
            )
            current = dao.get(task_id)
            if current is not None:
                _audit_task_event(
                    db,
                    current,
                    action="example.task.failed",
                    outcome="failure",
                    detail={
                        "task_id": task_id,
                        "processed_count": processed_count,
                        "success_count": success_count,
                        "failure_count": failure_count,
                        "error": error_message,
                    },
                )
            dao.append_log(task_id, level="error", message=error_message)

        context.run_db(fail)


def _load_async_task_input(db: Session, task_id: str) -> _AsyncTaskInput | None:
    """在 Session 关闭前提取后台任务执行所需字段。"""
    task = ExampleAsyncTaskDAO(db).get(task_id)
    if task is None:
        return None
    return _AsyncTaskInput(
        total_count=task.total_count,
        fail_every=task.fail_every,
        delay_ms=task.delay_ms,
        processed_count=task.processed_count,
        success_count=task.success_count,
        failure_count=task.failure_count,
    )


def _mark_task_cancelled(context: TaskContext, task_id: str) -> None:
    def cancel(db: Session) -> None:
        dao = ExampleAsyncTaskDAO(db)
        task = dao.get(task_id)
        if task is not None and task.status == "pending":
            dao.mark_failed(
                task_id,
                processed_count=task.processed_count,
                success_count=task.success_count,
                failure_count=task.failure_count,
                last_message="后台任务提交被取消",
            )
            dao.append_log(task_id, level="error", message="后台任务提交被取消")

    context.run_db(cancel)


def _audit_task_event(
    db: Session,
    task: ExampleAsyncTask,
    *,
    action: str,
    outcome: str,
    detail: dict,
) -> None:
    actor_username = None
    if task.requested_by_user_id is not None:
        user = db.query(User).filter(User.id == task.requested_by_user_id).first()
        actor_username = user.username if user is not None else None

    audit_service.create_event(
        db,
        outcome=outcome,
        action=action,
        actor_user_id=task.requested_by_user_id,
        actor_username=actor_username,
        resource_type="example_async_task",
        resource_id=task.id,
        target_summary=task.name,
        detail=detail,
    )
