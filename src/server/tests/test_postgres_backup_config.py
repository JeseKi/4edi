"""Regression tests for the pgBackRest Compose configuration generator."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_GENERATOR = PROJECT_ROOT / "docker/postgres-backup/generate-pgbackrest-config.sh"


def _run_generator(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    config_path = tmp_path / "pgbackrest.conf"
    status_dir = tmp_path / "status"
    environment = {
        "PATH": os.environ["PATH"],
        "PGBACKREST_CONFIG_PATH": str(config_path),
        "PG_BACKUP_STATUS_DIR": str(status_dir),
        "PG_BACKUP_LOCAL_PATH": str(tmp_path / "repository"),
        "PG_BACKUP_ENABLED": "true",
        "PG_BACKUP_MODE": "auto",
        "PG_BACKUP_REPO_CIPHER_PASS": "test-cipher-pass",
        "PG_BACKUP_AGE_RECIPIENT": "age1testrecipient",
        "POSTGRES_DB": "template",
    }
    environment.update(overrides)
    return subprocess.run(
        ["bash", str(CONFIG_GENERATOR)],
        check=False,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_backup_config_uses_local_repository_without_s3_settings(tmp_path: Path) -> None:
    result = _run_generator(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "status/repository-mode").read_text().strip() == "local"
    config = (tmp_path / "pgbackrest.conf").read_text()
    assert "repo1-type=posix" in config
    assert f"repo1-path={tmp_path / 'repository'}" in config
    assert "pg1-user=postgres" in config


def test_backup_config_uses_s3_only_when_the_configuration_is_complete(tmp_path: Path) -> None:
    result = _run_generator(
        tmp_path,
        PG_BACKUP_S3_BUCKET="backups",
        PG_BACKUP_S3_ENDPOINT="s3.example.test",
        PG_BACKUP_S3_ACCESS_KEY_ID="access-key",
        PG_BACKUP_S3_SECRET_ACCESS_KEY="secret-key",
        PG_BACKUP_S3_PREFIX="/production/template",
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "status/repository-mode").read_text().strip() == "s3"
    config = (tmp_path / "pgbackrest.conf").read_text()
    assert "repo1-type=s3" in config
    assert "repo1-path=/production/template/pgbackrest" in config
    assert "repo1-s3-bucket=backups" in config
    assert "repo1-storage-port=443" in config


def test_backup_config_rejects_partial_s3_settings(tmp_path: Path) -> None:
    result = _run_generator(tmp_path, PG_BACKUP_S3_BUCKET="backups")

    assert result.returncode != 0
    assert "S3 backup settings are incomplete" in result.stderr


def test_backup_config_rejects_an_s3_url_instead_of_a_host_name(tmp_path: Path) -> None:
    result = _run_generator(
        tmp_path,
        PG_BACKUP_MODE="s3",
        PG_BACKUP_S3_BUCKET="backups",
        PG_BACKUP_S3_ENDPOINT="https://s3.example.test",
        PG_BACKUP_S3_ACCESS_KEY_ID="access-key",
        PG_BACKUP_S3_SECRET_ACCESS_KEY="secret-key",
    )

    assert result.returncode != 0
    assert "must be a host name" in result.stderr


def test_backup_config_rejects_an_invalid_tls_verification_value(tmp_path: Path) -> None:
    result = _run_generator(
        tmp_path,
        PG_BACKUP_MODE="s3",
        PG_BACKUP_S3_BUCKET="backups",
        PG_BACKUP_S3_ENDPOINT="s3.example.test",
        PG_BACKUP_S3_ACCESS_KEY_ID="access-key",
        PG_BACKUP_S3_SECRET_ACCESS_KEY="secret-key",
        PG_BACKUP_S3_VERIFY_TLS="true",
    )

    assert result.returncode != 0
    assert "PG_BACKUP_S3_VERIFY_TLS must be y or n" in result.stderr
