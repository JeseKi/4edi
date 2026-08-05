from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from src.server.database_executor import DatabaseExecutor


pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.xdist_group(name="postgresql-integration"),
]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_postgresql_migration_path() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("未设置 TEST_DATABASE_URL，跳过 PostgreSQL 集成测试")

    url = make_url(database_url)
    assert url.get_backend_name() == "postgresql"
    assert url.database and "test" in url.database.lower(), "TEST_DATABASE_URL 必须指向测试数据库"
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    database_url = url.render_as_string(hide_password=False)
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": database_url,
    }
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
        )
        engine = create_engine(database_url)
        try:
            assert "users" in inspect(engine).get_table_names()
            assert "background_jobs" in inspect(engine).get_table_names()
        finally:
            engine.dispose()
    finally:
        subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "base"],
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
        )


def test_postgresql_executor_statement_timeout() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("未设置 TEST_DATABASE_URL，跳过 PostgreSQL 集成测试")

    url = make_url(database_url)
    assert url.get_backend_name() == "postgresql"
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    engine = create_engine(url)
    executor = DatabaseExecutor(
        sessionmaker(bind=engine, autocommit=False, autoflush=False),
        dialect="postgresql",
        max_workers=1,
        queue_timeout_seconds=5,
        statement_timeout_seconds=1,
    )

    async def run() -> None:
        try:
            with pytest.raises(OperationalError):
                await executor.run(
                    lambda db: db.execute(text("select pg_sleep(2)"))
                )
            assert await executor.run(
                lambda db: db.execute(text("select 1")).scalar_one()
            ) == 1
        finally:
            await executor.shutdown()

    try:
        asyncio.run(run())
    finally:
        engine.dispose()
