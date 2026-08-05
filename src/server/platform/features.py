"""内置功能包目录及其唯一装配入口。

功能包只能通过本模块暴露的 ``FeatureSpec`` 加入 Web 或 worker。这样 Web
进程与 worker 不会再分别硬编码业务模块导入，也让功能开关和依赖校验可测。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter

if TYPE_CHECKING:
    from src.server.task_runtime.runtime import TaskDefinition
else:
    TaskDefinition = Any


RouterLoader = Callable[[], tuple[APIRouter, ...]]
TaskLoader = Callable[[], tuple[TaskDefinition, ...]]


@dataclass(frozen=True)
class FeatureSpec:
    """一个可选功能包的公开装配描述。"""

    name: str
    requires: frozenset[str]
    routers: RouterLoader
    task_definitions: TaskLoader = lambda: ()
    dev_only: bool = False


def _routers(*loaders: Callable[[], APIRouter]) -> RouterLoader:
    return lambda: tuple(loader() for loader in loaders)


def _no_tasks() -> tuple[TaskDefinition, ...]:
    return ()


def _auth_router() -> APIRouter:
    from src.server.auth.router import router

    return router


def _admin_router() -> APIRouter:
    from src.server.admin.router import router

    return router


def _scope_router() -> APIRouter:
    from src.server.scope_management.router import router

    return router


def _audit_router() -> APIRouter:
    from src.server.audit.router import router

    return router


def _oauth_login_router() -> APIRouter:
    from src.server.oauth.router import router

    return router


def _oauth_provider_router() -> APIRouter:
    from src.server.oauth_provider.router import router

    return router


def _files_router() -> APIRouter:
    from src.server.files.router import router

    return router


def _example_router() -> APIRouter:
    from src.server.example_module.router import router

    return router


def _dev_provider_router() -> APIRouter:
    from src.server.providers.router import router

    return router


def _frontend_error_reporting_router() -> APIRouter:
    from src.server.frontend_error_reporting.router import router

    return router


def _notifications_router() -> APIRouter:
    from src.server.notifications.router import router

    return router


def _file_tasks() -> tuple[TaskDefinition, ...]:
    from src.server.files.service import DELETE_FILE_OBJECT, EXPIRE_PENDING_FILE

    return (EXPIRE_PENDING_FILE, DELETE_FILE_OBJECT)


def _example_tasks() -> tuple[TaskDefinition, ...]:
    from src.server.example_module.service import EXAMPLE_ASYNC_TASK

    return (EXAMPLE_ASYNC_TASK,)


FEATURE_CATALOG: dict[str, FeatureSpec] = {
    "auth": FeatureSpec("auth", frozenset(), _routers(_auth_router)),
    "admin": FeatureSpec(
        "admin", frozenset({"auth"}), _routers(_admin_router, _scope_router)
    ),
    "audit": FeatureSpec("audit", frozenset({"auth"}), _routers(_audit_router)),
    "oauth-login": FeatureSpec(
        "oauth-login", frozenset({"auth"}), _routers(_oauth_login_router)
    ),
    "oauth-provider": FeatureSpec(
        "oauth-provider", frozenset({"auth"}), _routers(_oauth_provider_router)
    ),
    "files": FeatureSpec(
        "files", frozenset({"auth"}), _routers(_files_router), _file_tasks
    ),
    "example": FeatureSpec(
        "example", frozenset({"auth"}), _routers(_example_router), _example_tasks
    ),
    "frontend-error-reporting": FeatureSpec(
        "frontend-error-reporting", frozenset(), _routers(_frontend_error_reporting_router)
    ),
    "notifications": FeatureSpec(
        "notifications", frozenset({"auth"}), _routers(_notifications_router)
    ),
    "dev-providers": FeatureSpec(
        "dev-providers", frozenset(), _routers(_dev_provider_router), dev_only=True
    ),
}


def resolve_features(
    configured: Iterable[str], *, app_env: str
) -> tuple[FeatureSpec, ...]:
    """解析、去重并校验功能包依赖，结果按目录声明顺序返回。"""
    requested = {name.strip().lower() for name in configured if name.strip()}
    if "all" in requested:
        requested.remove("all")
        requested.update(
            name
            for name, spec in FEATURE_CATALOG.items()
            if app_env == "dev" or not spec.dev_only
        )
    unknown = requested - FEATURE_CATALOG.keys()
    if unknown:
        raise ValueError(f"未知功能包：{', '.join(sorted(unknown))}")
    for name in requested:
        spec = FEATURE_CATALOG[name]
        missing = spec.requires - requested
        if missing:
            raise ValueError(
                f"功能包 {name} 缺少依赖：{', '.join(sorted(missing))}"
            )
        if spec.dev_only and app_env != "dev":
            raise ValueError(f"功能包 {name} 仅允许在 dev 环境启用")
    return tuple(spec for name, spec in FEATURE_CATALOG.items() if name in requested)


def task_definitions_for(features: Iterable[FeatureSpec]) -> tuple[TaskDefinition, ...]:
    """从已解析功能包收集任务，并拒绝重复任务名。"""
    definitions: list[TaskDefinition] = []
    names: set[str] = set()
    for feature in features:
        for definition in feature.task_definitions():
            if definition.name in names:
                raise ValueError(f"后台任务名称重复注册：{definition.name}")
            names.add(definition.name)
            definitions.append(definition)
    return tuple(definitions)
