# -*- coding: utf-8 -*-
"""
pytest 公共 fixtures（模板版）

功能：
- 统一测试环境变量
- 提供由 SQLite schema 模板复制的隔离数据库、会话与 TestClient
- 引导默认管理员

公开接口：
- `test_db_engine`
- `test_database_template`
- `test_db_session`
- `test_client`
- `init_test_database`
"""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# 测试环境配置
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ENABLED_FEATURES", "all")
os.environ.setdefault("ALLOWED_ORIGINS", '["http://localhost:3000"]')
os.environ["TURNSTILE_ENABLED"] = "false"
os.environ.setdefault(
    "EXTERNAL_PROVIDER_MOCK_LIST",
    '["github_oauth", "google_oauth", "turnstile", "mail", "example_external_api"]',
)


class SyncASGITestClient:
    """为同步 pytest 用例提供基于 httpx 的最小 ASGI client 包装。"""

    def __init__(self, app):
        self._loop = asyncio.new_event_loop()
        self._transport = httpx.ASGITransport(app=app)
        self._client = httpx.AsyncClient(
            transport=self._transport,
            base_url="http://testserver",
            follow_redirects=True,
        )

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def get(self, *args, **kwargs):
        return self._run(self._client.get(*args, **kwargs))

    def post(self, *args, **kwargs):
        # 旧业务测试代表已经主动确认当前协议的正常注册流程；在测试客户端
        # 边界补齐版本，避免非认证用例重复协议样板。合规用例可用专用 header
        # 禁用默认值，验证后端对缺失字段的 422 响应。
        path = str(args[0]) if args else str(kwargs.get("url", ""))
        headers = dict(kwargs.get("headers") or {})
        omit_defaults = headers.pop("X-Test-Omit-Legal-Versions", None)
        if headers:
            kwargs["headers"] = headers
        elif "headers" in kwargs:
            kwargs.pop("headers")
        if (
            not omit_defaults
            and path
            in {
                "/api/auth/register",
                "/api/auth/register-with-code",
                "/api/auth/register-with-phone-code",
            }
            and isinstance(kwargs.get("json"), dict)
        ):
            payload = dict(kwargs["json"])
            payload.setdefault("user_agreement_version", "2026-09-02")
            payload.setdefault("privacy_policy_version", "2026-09-02")
            kwargs["json"] = payload
        return self._run(self._client.post(*args, **kwargs))

    def put(self, *args, **kwargs):
        return self._run(self._client.put(*args, **kwargs))

    def patch(self, *args, **kwargs):
        return self._run(self._client.patch(*args, **kwargs))

    def delete(self, *args, **kwargs):
        return self._run(self._client.delete(*args, **kwargs))

    def request(self, *args, **kwargs):
        return self._run(self._client.request(*args, **kwargs))

    @property
    def cookies(self):
        return self._client.cookies

    def close(self) -> None:
        self._run(self._client.aclose())
        self._loop.close()


@pytest.fixture(autouse=True)
def disable_real_mail_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试期间统一禁用真实邮件发送，避免连接外部 SMTP。"""
    from src.server.mail.config import mail_config

    monkeypatch.setattr(mail_config, "sender_email", None, raising=False)
    monkeypatch.setattr(mail_config, "sender_password", None, raising=False)


def _create_test_sqlite_engine(database_path: Path) -> Engine:
    return create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )


@pytest.fixture(scope="session")
def test_database_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """创建一次 schema 模板，供同一 worker 的各测试复制。"""
    template_path = tmp_path_factory.mktemp("sqlite-template") / "template.db"
    engine = _create_test_sqlite_engine(template_path)

    from src.server.database import Base
    import src.server.auth.models  # noqa: F401
    import src.server.example_module.models  # noqa: F401
    import src.server.scope_management.models  # noqa: F401
    import src.server.oauth.models  # noqa: F401
    import src.server.oauth_provider.models  # noqa: F401
    import src.server.providers.models  # noqa: F401
    import src.server.audit.models  # noqa: F401
    import src.server.task_runtime.models  # noqa: F401
    import src.server.files.models  # noqa: F401
    import src.server.notifications.models  # noqa: F401
    import src.server.mall.models  # noqa: F401
    import src.server.information.models  # noqa: F401
    import src.server.complaint.models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)

        TestingSessionLocal = sessionmaker(
            bind=engine, autocommit=False, autoflush=False
        )
        session = TestingSessionLocal()
        try:
            from src.server.providers.service import sync_external_providers

            sync_external_providers(session)
            session.commit()
        finally:
            session.close()
    finally:
        engine.dispose()

    return template_path


@pytest.fixture(scope="function")
def test_db_engine(
    tmp_path: Path, test_database_template: Path
) -> Iterator[Engine]:
    """由 schema 模板复制出每用例独立的 SQLite 数据库。"""
    database_path = tmp_path / "test.db"
    shutil.copyfile(test_database_template, database_path)
    engine = _create_test_sqlite_engine(database_path)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine: Engine) -> Iterator[Session]:
    """提供测试数据库会话。"""
    TestingSessionLocal = sessionmaker(
        bind=test_db_engine, autocommit=False, autoflush=False
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def test_client(
    test_db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Iterator[SyncASGITestClient]:
    """提供一个配置了测试数据库的 FastAPI TestClient。"""
    from src.server.main import app
    from src.server.database_executor import DatabaseExecutor
    from src.server.example_module.service import EXAMPLE_ASYNC_TASK
    from src.server.files.service import DELETE_FILE_OBJECT, EXPIRE_PENDING_FILE
    from src.server.mail import MailDeliveryExecutor
    from src.server.mall.service import (
        MALL_COUPON_EXPIRE,
        MALL_ORDER_AUTO_CONFIRM,
        MALL_ORDER_PAYMENT_TIMEOUT,
        MALL_REFUND_AUTO_AGREE,
    )
    from src.server.platform.runtime import ApplicationRuntime
    from src.server.config import global_config
    from src.server.auth.service import sms
    from src.server.task_runtime import TaskRuntime

    # 测试不应因开发机遗留的商户凭据而调用微信支付网络接口。
    monkeypatch.setattr(global_config.mall, "payment_mode", "mock")
    # 同理，手机号流程测试只验证本地验证码逻辑，不发送真实短信。
    monkeypatch.setattr(sms, "is_tencent_sms_configured", lambda: False)
    client = SyncASGITestClient(app)
    TestTaskSession = sessionmaker(bind=test_db_session.get_bind(), autocommit=False, autoflush=False)

    def run_test_task_db(operation):
        task_db = TestTaskSession()
        try:
            result = operation(task_db)
            task_db.commit()
            return result
        except Exception:
            task_db.rollback()
            raise
        finally:
            task_db.close()

    database_executor = DatabaseExecutor(
        TestTaskSession,
        dialect="sqlite",
        max_workers=1,
        queue_timeout_seconds=30,
    )
    mail_delivery_executor = MailDeliveryExecutor(max_workers=2, queue_timeout_seconds=30)
    task_runtime = TaskRuntime(
        definitions=(
            EXAMPLE_ASYNC_TASK,
            EXPIRE_PENDING_FILE,
            DELETE_FILE_OBJECT,
            MALL_ORDER_PAYMENT_TIMEOUT,
            MALL_ORDER_AUTO_CONFIRM,
            MALL_REFUND_AUTO_AGREE,
            MALL_COUPON_EXPIRE,
        ),
        session_runner=run_test_task_db,
    )
    app.state.runtime = ApplicationRuntime(
        settings=global_config,
        enabled_features=frozenset({"auth", "admin", "audit", "oauth-login", "oauth-provider", "files", "example", "notifications", "mall", "information"}),
        database_executor=database_executor,
        mail_delivery_executor=mail_delivery_executor,
        task_runtime=task_runtime,
    )
    client._run(task_runtime.start())
    try:
        yield client
    finally:
        client._run(task_runtime.stop())
        client._run(database_executor.shutdown())
        client._run(mail_delivery_executor.shutdown())
        client.close()
        del app.state.runtime


@pytest.fixture(scope="function")
def init_test_database(test_db_engine) -> None:
    """初始化默认管理员等必要基础数据。"""
    TestingSessionLocal = sessionmaker(
        bind=test_db_engine, autocommit=False, autoflush=False
    )
    session = TestingSessionLocal()
    try:
        from src.server.auth.models import User
        from src.server.auth.schemas import UserRole

        exists = session.query(User).order_by(User.id.asc()).first()
        if not exists:
            admin = User(
                username="admin",
                email="admin@example.com",
                name="默认管理员",
                role=UserRole.SUPER_ADMIN,
            )
            admin.set_password("admin123")
            session.add(admin)
            session.commit()
    finally:
        session.close()
