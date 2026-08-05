"""统一的 SQLite / PostgreSQL 数据库基础设施。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.server.config import GlobalConfig, global_config
from src.server.database_executor import DatabaseExecutor
from src.server.schemas import DatabaseInfo

Base: Any = declarative_base()
_SessionResult = TypeVar("_SessionResult")
_POSTGRES_DEFAULTS = (5, 5, 30, 1800)
# SQLite 仅作为低频本地开发/轻量部署选项；该保护性等待无需暴露为运行时容量配置。
SQLITE_BUSY_TIMEOUT_SECONDS = 5


def _configure_sqlite_connection(engine: Engine) -> None:
    """为共享本地 SQLite 文件启用安全的多进程访问基础配置。"""

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_SECONDS * 1000}")
        finally:
            cursor.close()


def resolve_database_url(config: GlobalConfig = global_config) -> URL:
    """解析并校验唯一支持的 SQLite / PostgreSQL 连接 URL。"""
    try:
        url = make_url(config.database.url)
    except Exception as exc:
        raise ValueError("DATABASE_URL 不是有效的 SQLAlchemy URL") from exc

    backend = url.get_backend_name()
    if backend not in {"sqlite", "postgresql"}:
        raise ValueError("DATABASE_URL 仅支持 sqlite 或 postgresql")
    if backend == "postgresql" and url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


class DatabaseRuntime:
    """集中管理 Engine、Session 与方言特定的连接配置。"""

    def __init__(
        self,
        config: GlobalConfig = global_config,
        *,
        postgres_pool_settings: tuple[int, int, int, int] | None = None,
    ) -> None:
        self.config = config
        self.url = resolve_database_url(config)
        self.dialect = self.url.get_backend_name()
        self._postgres_pool_settings_override = postgres_pool_settings
        self.engine = self._build_engine()
        self.session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    @property
    def is_sqlite(self) -> bool:
        return self.dialect == "sqlite"

    @property
    def sqlite_path(self) -> Path | None:
        database = self.url.database
        if not self.is_sqlite or database in {None, ":memory:"}:
            return None
        assert database is not None
        path = Path(database)
        return path if path.is_absolute() else Path.cwd() / path

    @property
    def display_url(self) -> str:
        return self.url.render_as_string(hide_password=True)

    def _build_engine(self) -> Engine:
        if self.is_sqlite:
            engine = create_engine(
                self.url,
                connect_args={
                    "check_same_thread": False,
                    "timeout": SQLITE_BUSY_TIMEOUT_SECONDS,
                },
                echo=False,
            )
            _configure_sqlite_connection(engine)
            return engine

        pool_size, max_overflow, timeout, recycle = self._postgres_pool_settings()
        return create_engine(
            self.url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=timeout,
            pool_recycle=recycle,
            pool_pre_ping=True,
            echo=False,
        )

    def _postgres_pool_settings(self) -> tuple[int, int, int, int]:
        if self._postgres_pool_settings_override is not None:
            return self._postgres_pool_settings_override
        configured = (
            self.config.database.pool_size,
            self.config.database.max_overflow,
            self.config.database.pool_timeout_seconds,
            self.config.database.pool_recycle_seconds,
        )
        if self.config.app.env == "prod" and any(value is None for value in configured):
            raise ValueError(
                "生产 PostgreSQL 必须显式设置 DATABASE_POOL_SIZE、"
                "DATABASE_MAX_OVERFLOW、DATABASE_POOL_TIMEOUT_SECONDS 和 "
                "DATABASE_POOL_RECYCLE_SECONDS"
            )
        return tuple(
            default if value is None else value
            for value, default in zip(configured, _POSTGRES_DEFAULTS, strict=True)
        )  # type: ignore[return-value]

    def new_session(self) -> Session:
        return self.session_factory()

    def dispose(self) -> None:
        self.engine.dispose()


database_runtime = DatabaseRuntime()
engine = database_runtime.engine


def run_in_new_session(operation: Callable[[Session], _SessionResult]) -> _SessionResult:
    """在受控短事务中执行操作；成功提交，失败回滚并始终关闭。"""
    return run_in_session_factory(database_runtime.session_factory, operation)


def run_in_session_factory(
    session_factory: Callable[[], Session], operation: Callable[[Session], _SessionResult]
) -> _SessionResult:
    """在给定 Session 工厂创建的受控短事务中执行操作。"""
    db = session_factory()
    try:
        result = operation(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_task_database_runtime(
    config: GlobalConfig = global_config,
) -> DatabaseRuntime:
    """创建仅供后台 worker 使用的独立数据库运行时。"""
    return DatabaseRuntime(
        config,
        postgres_pool_settings=(
            config.task_database.pool_size,
            config.task_database.max_overflow,
            config.task_database.pool_timeout_seconds,
            config.task_database.pool_recycle_seconds,
        ),
    )


def create_database_executor(
    config: GlobalConfig = global_config,
    *,
    runtime: DatabaseRuntime = database_runtime,
) -> DatabaseExecutor:
    """创建 Web 进程唯一的受控 HTTP 数据库执行器。"""
    if runtime.is_sqlite:
        max_workers = 1
    else:
        pool_size, max_overflow, _, _ = runtime._postgres_pool_settings()
        available_connections = pool_size + max_overflow
        max_workers = config.database.executor_max_workers
        if max_workers > available_connections:
            raise ValueError(
                "DATABASE_EXECUTOR_MAX_WORKERS 不能超过 "
                "DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW"
            )

    return DatabaseExecutor(
        runtime.session_factory,
        dialect=runtime.dialect,
        max_workers=max_workers,
        queue_timeout_seconds=config.database.executor_queue_timeout_seconds,
        statement_timeout_seconds=(
            config.database.executor_statement_timeout_seconds
            if runtime.dialect == "postgresql"
            else None
        ),
    )


def bootstrap_database_data() -> None:
    """引导首次部署所需的管理员账号，不同步可选功能的运行时数据。"""

    def bootstrap(db: Session) -> None:
        from src.server.auth.service.bootstrap import bootstrap_default_admin

        bootstrap_default_admin(db)

    run_in_new_session(bootstrap)


def init_database() -> None:
    """仅供测试环境用 SQLite 建表；非测试环境必须使用 Alembic。"""
    is_test_env = os.getenv("PYTEST_CURRENT_TEST") or global_config.app.env == "test"
    sqlite_path = database_runtime.sqlite_path
    if is_test_env and sqlite_path is not None:
        database_runtime.dispose()
        if sqlite_path.exists():
            sqlite_path.unlink()
            logger.info("测试环境：已删除 SQLite 数据库文件")
        import_all_models()
        Base.metadata.create_all(bind=engine)
        bootstrap_database_data()
        return
    logger.warning("非测试 SQLite 环境不会自动建表，请先运行 Alembic 迁移")
    bootstrap_database_data()


def import_all_models() -> None:
    """导入所有模型，供 Alembic 与测试建表使用。"""
    from src.server.audit import models as _1  # noqa: F401
    from src.server.auth import models as _2  # noqa: F401
    from src.server.example_module import models as _3  # noqa: F401
    from src.server.oauth import models as _4  # noqa: F401
    from src.server.oauth_provider import models as _5  # noqa: F401
    from src.server.providers import models as _6  # noqa: F401
    from src.server.scope_management import models as _7  # noqa: F401
    from src.server.task_runtime import models as _8  # noqa: F401
    from src.server.files import models as _9  # noqa: F401
    from src.server.notifications import models as _10  # noqa: F401


def get_database_info() -> DatabaseInfo:
    """返回不含凭据的数据库目标信息。"""
    sqlite_path = database_runtime.sqlite_path
    return DatabaseInfo(
        dialect=database_runtime.dialect,
        database_url=database_runtime.display_url,
        database_exists=sqlite_path.exists() if sqlite_path is not None else None,
        database_size=sqlite_path.stat().st_size if sqlite_path is not None and sqlite_path.exists() else None,
    )
