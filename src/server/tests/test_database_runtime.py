from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from src.server.config import GlobalConfig
from src.server.database import (
    DatabaseRuntime,
    create_database_executor,
    create_task_database_runtime,
    resolve_database_url,
)


def test_database_url_has_a_single_sqlite_default() -> None:
    config = GlobalConfig()

    url = resolve_database_url(config)

    assert url.get_backend_name() == "sqlite"
    assert url.database == "data/database.db"


def test_database_runtime_uses_sqlite_specific_connect_args(tmp_path: Path) -> None:
    runtime = DatabaseRuntime(
        GlobalConfig(
            database_url=f"sqlite:///{tmp_path / 'template.db'}",
        )
    )
    try:
        with runtime.engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar_one() == 1
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
            assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
        assert runtime.sqlite_path == tmp_path / "template.db"
    finally:
        runtime.dispose()


def test_only_sqlite_and_postgresql_urls_are_accepted() -> None:
    with pytest.raises(ValueError, match="仅支持"):
        resolve_database_url(GlobalConfig(database_url="mysql://localhost/template"))


def test_production_postgresql_requires_explicit_pool_settings() -> None:
    with pytest.raises(ValueError, match="必须显式设置"):
        DatabaseRuntime(
            GlobalConfig(
                app_env="prod",
                database_url="postgresql+psycopg://user:password@localhost/template",
                database_pool_size=None,
                database_max_overflow=None,
                database_pool_timeout_seconds=None,
                database_pool_recycle_seconds=None,
            )
        )


def test_task_runtime_has_its_own_postgresql_connection_budget() -> None:
    config = GlobalConfig(
        database_url="postgresql+psycopg://user:password@localhost/template",
        database_pool_size=8,
        database_max_overflow=4,
        database_pool_timeout_seconds=30,
        database_pool_recycle_seconds=1800,
        task_database_pool_size=2,
        task_database_max_overflow=0,
        task_database_pool_timeout_seconds=5,
        task_database_pool_recycle_seconds=900,
    )

    runtime = create_task_database_runtime(config)
    try:
        assert runtime._postgres_pool_settings() == (2, 0, 5, 900)
    finally:
        runtime.dispose()


def test_web_executor_respects_postgresql_connection_budget() -> None:
    config = GlobalConfig(
        database_url="postgresql+psycopg://user:password@localhost/template",
        database_pool_size=3,
        database_max_overflow=1,
        database_pool_timeout_seconds=30,
        database_pool_recycle_seconds=1800,
        database_executor_max_workers=4,
    )
    runtime = DatabaseRuntime(config)
    executor = create_database_executor(config, runtime=runtime)
    try:
        assert executor.max_workers == 4
        assert executor.queue_timeout_seconds == 30
        assert executor.statement_timeout_seconds == 60
    finally:
        executor._thread_pool.shutdown(wait=False, cancel_futures=True)
        runtime.dispose()


def test_web_executor_rejects_postgresql_worker_count_above_pool_budget() -> None:
    config = GlobalConfig(
        database_url="postgresql+psycopg://user:password@localhost/template",
        database_pool_size=2,
        database_max_overflow=0,
        database_pool_timeout_seconds=30,
        database_pool_recycle_seconds=1800,
        database_executor_max_workers=3,
    )
    runtime = DatabaseRuntime(config)
    try:
        with pytest.raises(ValueError, match="DATABASE_EXECUTOR_MAX_WORKERS"):
            create_database_executor(config, runtime=runtime)
    finally:
        runtime.dispose()
