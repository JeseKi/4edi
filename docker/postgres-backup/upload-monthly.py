#!/usr/bin/env python3
"""Upload one encrypted logical dump and retain the newest monthly snapshots."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import boto3  # type: ignore[import-untyped]
import urllib3


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"{name} is required for S3 monthly snapshot upload")
    return value


def _endpoint_url() -> str:
    endpoint = _required("PG_BACKUP_S3_ENDPOINT")
    port = os.environ.get("PG_BACKUP_S3_PORT", "443")
    return f"https://{endpoint}:{port}"


def _verify_tls() -> bool:
    return os.environ.get("PG_BACKUP_S3_VERIFY_TLS", "y").lower() in {
        "y",
        "yes",
        "true",
        "1",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--retain", type=int, default=12)
    args = parser.parse_args()

    if args.retain < 1:
        raise SystemExit("--retain must be at least 1")
    if not args.file.is_file():
        raise SystemExit(f"monthly snapshot not found: {args.file}")

    client = boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        region_name=os.environ.get("PG_BACKUP_S3_REGION", "us-east-1"),
        aws_access_key_id=_required("PG_BACKUP_S3_ACCESS_KEY_ID"),
        aws_secret_access_key=_required("PG_BACKUP_S3_SECRET_ACCESS_KEY"),
        verify=_verify_tls(),
    )
    if not _verify_tls():
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    bucket = _required("PG_BACKUP_S3_BUCKET")
    client.upload_file(str(args.file), bucket, args.key)

    prefix = args.key.rsplit("/", 1)[0] + "/"
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(item["Key"] for item in page.get("Contents", []))

    stale_keys = sorted(keys, reverse=True)[args.retain :]
    if stale_keys:
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": key} for key in stale_keys], "Quiet": True},
        )


if __name__ == "__main__":
    main()
