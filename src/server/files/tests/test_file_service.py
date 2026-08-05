from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.server.auth.dependencies import AuthenticatedPrincipal
from src.server.config import GlobalConfig
from src.server.files import service
from src.server.files.schemas import FileUploadIntentCreate
from src.server.files.storage import LocalFileStorage, S3FileStorage, StoredObject as StorageObject
from src.server.files.service import DELETE_FILE_OBJECT, EXPIRE_PENDING_FILE
from src.server.task_runtime import TaskRuntime
from src.server.task_runtime.models import BackgroundJob


def _principal(user_id: int, role: str = "user") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id=user_id,
        username=f"user-{user_id}",
        role=role,
        email=f"user-{user_id}@example.com",
        two_factor_enabled=False,
    )


def _runtime() -> TaskRuntime:
    return TaskRuntime(definitions=(EXPIRE_PENDING_FILE, DELETE_FILE_OBJECT))


def test_local_upload_complete_and_authorization(test_db_session: Session, tmp_path):
    runtime = _runtime()
    asset = service.create_upload_intent(
        test_db_session,
        runtime,
        FileUploadIntentCreate(filename="hello.txt", size_bytes=5),
        _principal(1),
    )
    test_db_session.commit()

    job = test_db_session.query(BackgroundJob).filter_by(resource_id=asset.id).one()
    assert job.status == "retry_wait"
    assert job.next_attempt_at is not None
    assert job.next_attempt_at > datetime.now(timezone.utc).replace(tzinfo=None)

    snapshot = service.get_snapshot_for_upload(test_db_session, asset.id, _principal(1))
    storage = LocalFileStorage(tmp_path)
    service.store_local_upload(snapshot, BytesIO(b"hello"), storage)
    stored = storage.inspect(snapshot.storage_key)
    result, error = service.finalize_upload(
        test_db_session,
        runtime,
        _principal(1),
        asset.id,
        stored,
    )
    test_db_session.commit()

    assert error is None
    assert result.status == "available"
    assert storage.path_for_download(snapshot.storage_key).read_bytes() == b"hello"

    with pytest.raises(HTTPException) as exc:
        service.get_asset(test_db_session, asset.id, _principal(2))
    assert exc.value.status_code == 404
    assert service.get_asset(test_db_session, asset.id, _principal(2, role="admin")).id == asset.id


def test_rejected_upload_enqueues_object_deletion(test_db_session: Session):
    runtime = _runtime()
    asset = service.create_upload_intent(
        test_db_session,
        runtime,
        FileUploadIntentCreate(filename="bad.pdf", size_bytes=12),
        _principal(1),
    )
    test_db_session.flush()

    result, error = service.finalize_upload(
        test_db_session,
        runtime,
        _principal(1),
        asset.id,
        StorageObject(size_bytes=1),
    )
    test_db_session.commit()

    assert result.status == "rejected"
    assert error is not None
    jobs = test_db_session.query(BackgroundJob).filter_by(resource_id=asset.id).all()
    assert {job.task_name for job in jobs} == {
        EXPIRE_PENDING_FILE.name,
        DELETE_FILE_OBJECT.name,
    }


def test_s3_upload_target_has_exact_key_and_size_policy():
    storage = S3FileStorage(
        GlobalConfig(
            file_storage_driver="s3",
            file_s3_bucket="private-files",
            file_s3_region="us-east-1",
            file_s3_endpoint_url="https://objects.example.test",
            file_s3_access_key_id="test-access-key",
            file_s3_secret_access_key="test-secret-key",
        )
    )
    target = storage.create_upload_target("file-assets/abc", "text/plain", 1024)

    assert target["fields"]["key"] == "file-assets/abc"
    assert target["fields"]["Content-Type"] == "text/plain"
    assert target["url"].startswith("https://objects.example.test")


def test_s3_bucket_endpoint_does_not_repeat_bucket_in_path():
    storage = S3FileStorage(
        GlobalConfig(
            file_storage_driver="s3",
            file_s3_bucket="private-files",
            file_s3_region="ap-guangzhou",
            file_s3_endpoint_url="https://private-files.cos.ap-guangzhou.myqcloud.com",
            file_s3_access_key_id="test-access-key",
            file_s3_secret_access_key="test-secret-key",
        )
    )

    target = storage.create_upload_target("file-assets/abc", "text/plain", 1024)

    assert target["url"] == "https://private-files.cos.ap-guangzhou.myqcloud.com/"


def test_docx_extension_is_accepted_without_client_mime(test_db_session: Session):
    asset = service.create_upload_intent(
        test_db_session,
        _runtime(),
        FileUploadIntentCreate(
            filename="医生个人简介.docx",
            size_bytes=1024,
        ),
        _principal(1),
    )

    assert asset.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert asset.storage_key.endswith(".docx")


def test_unknown_extension_is_rejected(test_db_session: Session):
    with pytest.raises(HTTPException) as exc:
        service.create_upload_intent(
            test_db_session,
            _runtime(),
            FileUploadIntentCreate(
                filename="untrusted.exe",
                size_bytes=1024,
            ),
            _principal(1),
        )
    assert exc.value.detail == "不支持 EXE 文件类型."
