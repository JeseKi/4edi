from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, case, or_, select, update
from sqlalchemy.orm import Session

from .models import BackgroundJob


@dataclass(frozen=True)
class ClaimedJob:
    id: str
    task_name: str
    queue_name: str
    attempt_count: int
    max_attempts: int
    metadata_json: str


class BackgroundJobDAO:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **values: Any) -> BackgroundJob:
        values.setdefault("metadata_json", "{}")
        job = BackgroundJob(**values)
        self.db.add(job)
        self.db.flush()
        return job

    def claim_next(self, queue_name: str, now: datetime) -> ClaimedJob | None:
        candidate = self.db.execute(
            select(
                BackgroundJob.id,
                BackgroundJob.task_name,
                BackgroundJob.queue_name,
                BackgroundJob.attempt_count,
                BackgroundJob.max_attempts,
                BackgroundJob.metadata_json,
            )
            .where(
                BackgroundJob.queue_name == queue_name,
                or_(
                    BackgroundJob.status == "queued",
                    and_(
                        BackgroundJob.status == "retry_wait",
                        BackgroundJob.next_attempt_at <= now,
                    ),
                ),
            )
            .order_by(BackgroundJob.created_at.asc(), BackgroundJob.id.asc())
            .limit(1)
        ).one_or_none()
        if candidate is None:
            return None
        candidate_id = candidate.id

        claimed = self.db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.id == candidate_id,
                or_(
                    BackgroundJob.status == "queued",
                    and_(
                        BackgroundJob.status == "retry_wait",
                        BackgroundJob.next_attempt_at <= now,
                    ),
                ),
            )
            .values(
                status="running",
                attempt_count=BackgroundJob.attempt_count + 1,
                started_at=case(
                    (BackgroundJob.started_at.is_(None), now),
                    else_=BackgroundJob.started_at,
                ),
                next_attempt_at=None,
                updated_at=now,
                error_type=None,
                error_message=None,
            )
        )
        if claimed.rowcount != 1:
            return None

        snapshot = ClaimedJob(
            id=candidate.id,
            task_name=candidate.task_name,
            queue_name=candidate.queue_name,
            attempt_count=candidate.attempt_count + 1,
            max_attempts=candidate.max_attempts,
            metadata_json=candidate.metadata_json,
        )
        return snapshot

    def recover_expired_leases(self, now: datetime, lease_seconds: int) -> int:
        cutoff = now - timedelta(seconds=lease_seconds)
        expired = self.db.execute(
            select(BackgroundJob).where(
                BackgroundJob.status == "running",
                BackgroundJob.updated_at < cutoff,
            )
        ).scalars()
        recovered = 0
        for job in expired:
            if job.attempt_count >= job.max_attempts:
                job.status = "failed"
                job.finished_at = now
                job.error_type = "LeaseExpired"
                job.error_message = "任务执行租约到期，且已达到最大尝试次数"
            else:
                job.status = "queued"
                job.next_attempt_at = now
                job.error_type = "LeaseExpired"
                job.error_message = "任务执行租约到期，已重新排队"
            job.updated_at = now
            recovered += 1
        return recovered

    def touch_running(self, job_id: str, now: datetime) -> bool:
        result = self.db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == job_id, BackgroundJob.status == "running")
            .values(updated_at=now)
        )
        if result.rowcount:
            return True
        return False

    def finish(self, job_id: str, status: str, *, error: Exception | None = None) -> None:
        now = datetime.now(timezone.utc)
        values: dict[str, Any] = {
            "status": status,
            "finished_at": now,
            "next_attempt_at": None,
            "updated_at": now,
        }
        if error is not None:
            values["error_type"] = error.__class__.__name__
            values["error_message"] = str(error)[:1000]
        self.db.execute(update(BackgroundJob).where(BackgroundJob.id == job_id).values(**values))

    def schedule_retry(self, job_id: str, error: Exception, next_attempt_at: datetime) -> None:
        self.db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == job_id)
            .values(
                status="retry_wait",
                next_attempt_at=next_attempt_at,
                error_type=error.__class__.__name__,
                error_message=str(error)[:1000],
                updated_at=datetime.now(timezone.utc),
            )
        )

    def fail_unrecoverable(self, job_id: str, error_type: str, message: str) -> None:
        now = datetime.now(timezone.utc)
        self.db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == job_id)
            .values(
                status="failed",
                finished_at=now,
                next_attempt_at=None,
                error_type=error_type,
                error_message=message[:1000],
                updated_at=now,
            )
        )
