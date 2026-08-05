import ast
from pathlib import Path

import pytest


SERVER_ROOT = Path(__file__).resolve().parents[1]
INFRASTRUCTURE_PATHS = {
    Path("conftest.py"),
    Path("database.py"),
    Path("database_executor.py"),
    Path("main.py"),
}
INFRASTRUCTURE_PACKAGES = {"task_runtime"}
FORBIDDEN_DATABASE_IMPORTS = {
    "sqlalchemy.create_engine",
    "sqlalchemy.create_async_engine",
    "sqlalchemy.orm.sessionmaker",
    "sqlalchemy.orm.async_sessionmaker",
    "sqlalchemy.orm.scoped_session",
    "src.server.database.create_database_executor",
    "src.server.database.create_task_database_runtime",
    "src.server.database.database_runtime",
    "src.server.database.engine",
    "src.server.database.run_in_new_session",
    "src.server.database.run_in_session_factory",
}
FORBIDDEN_DATABASE_IMPORT_NAMES = {"get_db", "get_session_runner", "SessionLocal"}
FORBIDDEN_DATABASE_CALLS = {
    "sqlalchemy.create_engine",
    "sqlalchemy.create_async_engine",
    "sqlalchemy.orm.Session",
    "sqlalchemy.orm.sessionmaker",
    "sqlalchemy.orm.async_sessionmaker",
    "sqlalchemy.orm.scoped_session",
    "src.server.database.DatabaseRuntime",
    "src.server.database.create_database_executor",
    "src.server.database.create_task_database_runtime",
    "src.server.database.database_runtime.new_session",
    "src.server.database.run_in_new_session",
    "src.server.database.run_in_session_factory",
}
FORBIDDEN_DATABASE_REFERENCE_PREFIXES = {
    "src.server.database.database_runtime.",
    "src.server.database.engine.",
}
FORBIDDEN_TRANSACTION_METHODS = {"commit", "rollback"}


class _DatabaseTransactionVisitor(ast.NodeVisitor):
    """解析数据库入口的别名，禁止业务代码自行控制事务。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.aliases: dict[str, str] = {}
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".")[0]
            self.aliases[local_name] = alias.name if alias.asname else local_name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module
        if module is None:
            return
        for alias in node.names:
            imported_name = self._canonical_import_name(module, alias)
            local_name = alias.asname or alias.name
            self.aliases[local_name] = imported_name
            if (
                alias.name in FORBIDDEN_DATABASE_IMPORT_NAMES
                or imported_name in FORBIDDEN_DATABASE_IMPORTS
                or imported_name == "src.server.database"
            ):
                self._add(node, f"禁止导入 {imported_name}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        reference = self._resolve_reference(node.func)
        if reference in FORBIDDEN_DATABASE_CALLS or (
            reference is not None
            and any(
                reference.startswith(prefix)
                for prefix in FORBIDDEN_DATABASE_REFERENCE_PREFIXES
            )
        ):
            self._add(node, f"禁止调用 {reference}")
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in FORBIDDEN_TRANSACTION_METHODS
        ):
            self._add(node, f"禁止在业务代码中调用 .{node.func.attr}()")
        self.generic_visit(node)

    @staticmethod
    def _canonical_import_name(module: str, alias: ast.alias) -> str:
        if module == "src.server" and alias.name == "database":
            return "src.server.database"
        if module == "database" or module.endswith(".database"):
            return f"src.server.database.{alias.name}"
        return f"{module}.{alias.name}"

    def _resolve_reference(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            parent = self._resolve_reference(node.value)
            return f"{parent}.{node.attr}" if parent is not None else None
        return None

    def _add(self, node: ast.AST, reason: str) -> None:
        lineno = getattr(node, "lineno", 0)
        self.violations.append(f"{self.path}:{lineno}: {reason}")


def _find_database_transaction_violations(source: str, path: Path) -> list[str]:
    tree = ast.parse(source, filename=str(path))
    visitor = _DatabaseTransactionVisitor(path)
    visitor.visit(tree)
    return visitor.violations


def _iter_business_source_files() -> list[Path]:
    paths: list[Path] = []
    for path in SERVER_ROOT.rglob("*.py"):
        relative_path = path.relative_to(SERVER_ROOT)
        if "tests" in relative_path.parts:
            continue
        if relative_path in INFRASTRUCTURE_PATHS:
            continue
        if relative_path.parts[0] in INFRASTRUCTURE_PACKAGES:
            continue
        paths.append(path)
    return paths


def test_business_modules_use_controlled_database_transactions():
    violations: list[str] = []
    for path in _iter_business_source_files():
        violations.extend(
            _find_database_transaction_violations(
                path.read_text(encoding="utf-8"), path.relative_to(SERVER_ROOT)
            )
        )
    assert not violations, "业务模块必须使用受控数据库事务：\n" + "\n".join(violations)


@pytest.mark.parametrize(
    ("source", "expected_reason"),
    [
        (
            "from sqlalchemy.orm import sessionmaker as make_session\n"
            "make_session()\n",
            "sqlalchemy.orm.sessionmaker",
        ),
        (
            "import sqlalchemy.orm as orm\n"
            "orm.sessionmaker()\n",
            "sqlalchemy.orm.sessionmaker",
        ),
        (
            "import sqlalchemy.orm\n"
            "sqlalchemy.orm.sessionmaker()\n",
            "sqlalchemy.orm.sessionmaker",
        ),
        (
            "from src.server.database import run_in_new_session as run\n"
            "run(lambda db: None)\n",
            "src.server.database.run_in_new_session",
        ),
        (
            "from ..database import run_in_session_factory as run\n"
            "run(lambda: None, lambda db: None)\n",
            "src.server.database.run_in_session_factory",
        ),
        (
            "from src.server import database as database_module\n"
            "database_module.engine.connect()\n",
            "src.server.database",
        ),
        ("def save(db):\n    db.commit()\n", ".commit()"),
    ],
)
def test_database_transaction_guard_detects_aliases_and_manual_transactions(
    source: str, expected_reason: str
):
    violations = _find_database_transaction_violations(source, Path("sample.py"))

    assert any(expected_reason in violation for violation in violations)


def test_only_worker_process_starts_the_task_consumer():
    server_root = Path(__file__).resolve().parents[1]
    project_root = server_root.parents[1]
    web_source = (server_root / "main.py").read_text(encoding="utf-8")
    worker_source = (server_root / "task_runtime" / "worker.py").read_text(
        encoding="utf-8"
    )
    supervisor_source = (project_root / "run.py").read_text(encoding="utf-8")

    assert "await task_runtime.start()" not in web_source
    assert "await runtime.start()" in worker_source
    assert '"src.server.web"' in supervisor_source
    assert '"src.server.task_runtime.worker"' in supervisor_source


def test_task_registry_delegates_to_feature_catalog_instead_of_business_imports():
    registry_source = (
        Path(__file__).resolve().parents[1] / "task_runtime" / "registry.py"
    ).read_text(encoding="utf-8")

    assert "task_definitions_for" in registry_source
    assert "src.server.example_module.service" not in registry_source
    assert "src.server.files.service" not in registry_source
