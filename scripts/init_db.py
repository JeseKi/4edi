#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化/检查模板数据库的 CLI

用法：
- python scripts/init_db.py --check   # 检查表
- python scripts/init_db.py --reset   # 重置并迁移
- python scripts/init_db.py           # 迁移到最新版本并引导首个管理员
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from alembic import command
from alembic.config import Config
from loguru import logger

from src.server.database import bootstrap_database_data, database_runtime, engine

PROJECT_ROOT = Path(__file__).parent.parent


def upgrade_database() -> None:
    """执行 Alembic 迁移并引导首个管理员。"""
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    bootstrap_database_data()


def reset_database() -> None:
    """删除数据库文件并重新初始化。仅用于开发。"""
    db_path = database_runtime.sqlite_path
    if db_path is None:
        raise SystemExit("--reset 仅支持 SQLite；PostgreSQL 请使用受管数据库的显式重建流程")
    database_runtime.dispose()
    if db_path.exists():
        db_path.unlink()
        logger.info("已删除数据库文件：{}", db_path)
    upgrade_database()


def check_status() -> None:
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info("当前数据库表: {}", tables)


def main() -> None:
    parser = argparse.ArgumentParser(description="模板数据库工具")
    parser.add_argument(
        "--reset", action="store_true", help="重置数据库（删除后再初始化）"
    )
    parser.add_argument("--check", action="store_true", help="检查数据库状态")
    args = parser.parse_args()

    if args.check:
        check_status()
        return
    if args.reset:
        reset_database()
        return

    # 默认：迁移到最新版本并引导首个管理员
    upgrade_database()


if __name__ == "__main__":
    main()
