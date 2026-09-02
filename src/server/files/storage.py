from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit, urlunsplit

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from src.server.config import GlobalConfig, global_config


class FileStorageError(RuntimeError):
    pass


class FileObjectNotFoundError(FileStorageError):
    pass


@dataclass(frozen=True)
class StoredObject:
    size_bytes: int


class FileStorage:
    driver: str

    def create_upload_target(self, key: str, content_type: str, max_size: int):
        raise NotImplementedError

    def inspect(self, key: str) -> StoredObject:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def sha256(self, key: str) -> str:
        raise NotImplementedError


class LocalFileStorage(FileStorage):
    driver = "local"

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_upload_target(self, key: str, content_type: str, max_size: int):
        raise FileStorageError("local 存储不支持预签名上传目标")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path != self.root and self.root not in path.parents:
            raise FileStorageError("非法文件存储路径")
        return path

    def write_from_file(self, key: str, source: BinaryIO, max_size: int) -> int:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.part")
        written = 0
        try:
            with temporary.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_size:
                        raise FileStorageError("文件超过允许大小")
                    output.write(chunk)
            temporary.replace(target)
            return written
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def inspect(self, key: str) -> StoredObject:
        path = self._path(key)
        if not path.is_file():
            raise FileObjectNotFoundError("文件对象不存在")
        return StoredObject(size_bytes=path.stat().st_size)

    def path_for_download(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise FileObjectNotFoundError("文件对象不存在")
        return path

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def sha256(self, key: str) -> str:
        digest = hashlib.sha256()
        path = self.path_for_download(key)
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()


class S3FileStorage(FileStorage):
    driver = "s3"

    def __init__(self, config: GlobalConfig):
        if not config.files.s3_bucket:
            raise FileStorageError("FILE_S3_BUCKET 为 s3 存储必填")
        if bool(config.files.s3_access_key_id) != bool(config.files.s3_secret_access_key):
            raise FileStorageError("FILE_S3_ACCESS_KEY_ID 与 FILE_S3_SECRET_ACCESS_KEY 必须同时配置")
        self.bucket = config.files.s3_bucket
        client_options = {
            "service_name": "s3",
            "region_name": config.files.s3_region,
            "endpoint_url": config.files.s3_endpoint_url or None,
            "config": Config(s3={"addressing_style": config.files.s3_addressing_style}),
        }
        if config.files.s3_access_key_id:
            client_options["aws_access_key_id"] = config.files.s3_access_key_id
            client_options["aws_secret_access_key"] = config.files.s3_secret_access_key or None
        self.client = boto3.client(**client_options)
        self._bucket_endpoint_path_prefix = self._get_bucket_endpoint_path_prefix(
            config.files.s3_endpoint_url
        )
        if self._bucket_endpoint_path_prefix:
            self.client.meta.events.register(
                "before-sign.s3", self._remove_duplicate_bucket_path
            )
        self.presign_ttl_seconds = config.files.presign_ttl_seconds

    def _get_bucket_endpoint_path_prefix(self, endpoint_url: str) -> str | None:
        """Detect custom endpoints that already include the bucket in their host."""
        if not endpoint_url:
            return None
        hostname = urlsplit(endpoint_url).hostname
        if hostname and hostname.lower().startswith(f"{self.bucket.lower()}."):
            return f"/{self.bucket}"
        return None

    def _remove_duplicate_bucket_path(self, request, **_: object) -> None:
        """Use ``/key`` instead of ``/bucket/key`` for a bucket endpoint.

        COS bucket endpoints contain the bucket in the hostname.  With a custom
        endpoint, botocore may nevertheless produce a path-style URL, causing
        COS to store/read a different object than the one our record refers to.
        """
        prefix = self._bucket_endpoint_path_prefix
        if not prefix:
            return
        parsed = urlsplit(request.url)
        if parsed.path == prefix:
            path = "/"
        elif parsed.path.startswith(f"{prefix}/"):
            path = parsed.path[len(prefix) :]
        else:
            return
        request.url = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))

    def create_upload_target(self, key: str, content_type: str, max_size: int) -> dict:
        return self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_size],
                ["eq", "$key", key],
            ],
            ExpiresIn=self.presign_ttl_seconds,
        )

    def inspect(self, key: str) -> StoredObject:
        try:
            result = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise FileObjectNotFoundError("文件对象不存在") from exc
            raise FileStorageError("读取对象存储元数据失败") from exc
        return StoredObject(size_bytes=int(result["ContentLength"]))

    def download_url(self, key: str, filename: str) -> str:
        disposition = f'attachment; filename="{filename.replace(chr(34), "")}"'
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=self.presign_ttl_seconds,
        )

    def sha256(self, key: str) -> str:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                raise FileObjectNotFoundError("文件对象不存在") from exc
            raise FileStorageError("读取对象存储文件失败") from exc
        body = response["Body"]
        digest = hashlib.sha256()
        try:
            while chunk := body.read(1024 * 1024):
                digest.update(chunk)
        finally:
            body.close()
        return digest.hexdigest()

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise FileStorageError("删除对象存储文件失败") from exc


def get_file_storage(config: GlobalConfig = global_config) -> FileStorage:
    if config.files.storage_driver == "local":
        root = config.files.local_root
        if not root.is_absolute():
            root = config.app.project_root / root
        return LocalFileStorage(root)
    return S3FileStorage(config)
