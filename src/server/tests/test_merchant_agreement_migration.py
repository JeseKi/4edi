"""商家协议哈希字段迁移必须兼容已经执行的历史版本。"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _upgrade(database_path: Path, target: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path}"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", target],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def _columns(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(shop_agreements)")
    }


def test_agreement_hash_migration_preserves_existing_digest(tmp_path: Path) -> None:
    database_path = tmp_path / "merchant-migration.db"
    _upgrade(database_path, "merchant_flow14")

    with sqlite3.connect(database_path) as connection:
        assert "content_sha256" in _columns(connection)
        connection.execute(
            """
            INSERT INTO users (
                id, username, email, password_hash, role, status, created_at,
                token_version, two_factor_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                999,
                "migration-user",
                "migration@example.com",
                "not-a-real-password-hash",
                "USER",
                "ACTIVE",
                "2026-09-02 00:00:00",
                0,
                0,
            ),
        )
        connection.execute(
            """
            INSERT INTO mall_shops (
                id, owner_user_id, name, status, deposit_fen, created_at,
                updated_at, onboarding_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                999,
                999,
                "迁移测试商家",
                "PENDING",
                0,
                "2026-09-02 00:00:00",
                "2026-09-02 00:00:00",
                "agreement_generated",
            ),
        )
        connection.execute(
            """
            INSERT INTO shop_agreements (
                shop_id, agreement_number, document_version, content_markdown,
                content_sha256, status, generated_by_user_id, generated_at,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                999,
                "M-MIGRATION-TEST",
                "2026-09-02",
                "历史协议定稿",
                "a" * 64,
                "generated",
                999,
                "2026-09-02 00:00:00",
                "2026-09-02 00:00:00",
            ),
        )

    _upgrade(database_path, "head")

    with sqlite3.connect(database_path) as connection:
        columns = _columns(connection)
        assert "content_sha256" not in columns
        assert "draft_content_sha256" in columns
        assert "final_file_sha256" in columns
        assert "signature_mode" in columns
        assert "acceptance_ip" in columns
        assert "acceptance_user_agent" in columns
        row = connection.execute(
            """
            SELECT draft_content_sha256, final_file_sha256, signature_mode,
                   acceptance_ip, acceptance_user_agent
            FROM shop_agreements
            WHERE agreement_number = 'M-MIGRATION-TEST'
            """
        ).fetchone()
        assert row == ("a" * 64, None, "uploaded_document", None, None)
        shop = connection.execute(
            "SELECT current_agreement_id FROM mall_shops WHERE id = 999"
        ).fetchone()
        assert shop == (1,)
