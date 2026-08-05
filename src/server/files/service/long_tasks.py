from __future__ import annotations

from src.server.task_runtime import RetryableTaskError, TaskDefinition, TaskQueue

from ..storage import FileStorageError, get_file_storage


def _expire_pending_file(context, asset_id: str) -> None:
    from . import short_transactions as service

    snapshot = context.run_db(lambda db: service.mark_expired_if_pending(db, asset_id))
    if snapshot is None:
        return
    try:
        get_file_storage().delete(snapshot.storage_key)
    except FileStorageError as exc:
        raise RetryableTaskError(str(exc)) from exc


def _delete_file_object(context, asset_id: str) -> None:
    from . import short_transactions as service

    snapshot = context.run_db(lambda db: service.get_deletion_snapshot(db, asset_id))
    if snapshot is None:
        return
    try:
        get_file_storage().delete(snapshot.storage_key)
    except FileStorageError as exc:
        raise RetryableTaskError(str(exc)) from exc
    context.run_db(lambda db: service.mark_deleted(db, asset_id))


EXPIRE_PENDING_FILE = TaskDefinition(
    name="files.expire_pending_upload", queue=TaskQueue.IO, handler=_expire_pending_file
)
DELETE_FILE_OBJECT = TaskDefinition(
    name="files.delete_object", queue=TaskQueue.IO, handler=_delete_file_object
)
