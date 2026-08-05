#!/bin/sh
set -e

DB_DIALECT="$(python - <<'PY'
from src.server.config import global_config
from src.server.database import resolve_database_url

print(resolve_database_url(global_config).get_backend_name())
PY
)"

DB_PATH=""
if [ "$DB_DIALECT" = "sqlite" ]; then
DB_PATH="$(python - <<'PY'
from pathlib import Path

from src.server.config import global_config
from src.server.database import resolve_database_url

url = resolve_database_url(global_config)
if url.database and url.database != ":memory:":
    path = Path(url.database)
    print(path if path.is_absolute() else Path.cwd() / path)
PY
)"
fi

backup_database() {
    BACKUP_PATH="${DB_PATH}.bak"
    if [ ! -f "$DB_PATH" ]; then
        echo "未找到现有数据库，跳过备份"
        return 0
    fi

    echo "开始备份数据库..."
    rm -f "${BACKUP_PATH}.3"

    if [ -f "${BACKUP_PATH}.2" ]; then
        mv "${BACKUP_PATH}.2" "${BACKUP_PATH}.3"
    fi

    if [ -f "${BACKUP_PATH}.1" ]; then
        mv "${BACKUP_PATH}.1" "${BACKUP_PATH}.2"
    fi

    if [ -f "$BACKUP_PATH" ]; then
        mv "$BACKUP_PATH" "${BACKUP_PATH}.1"
    fi

    cp "$DB_PATH" "$BACKUP_PATH"
    echo "数据库备份完成: ${BACKUP_PATH}"
}

if [ "$DB_DIALECT" = "sqlite" ] && [ -n "$DB_PATH" ]; then
    # 确保 SQLite 数据库目录存在（volume 挂载时可能为空）
    mkdir -p "$(dirname "$DB_PATH")"
    backup_database
else
    echo "数据库方言为 ${DB_DIALECT}，跳过 SQLite 文件备份"
fi

# 运行数据库迁移。PostgreSQL 容器或外部数据库短暂不可用时会重试。
MIGRATION_RETRY_ATTEMPTS="$(python - <<'PY'
from src.server.config import global_config

print(global_config.database.migration_retry_attempts)
PY
)"
MIGRATION_RETRY_INTERVAL_SECONDS="$(python - <<'PY'
from src.server.config import global_config

print(global_config.database.migration_retry_interval_seconds)
PY
)"
attempt=1
while ! alembic upgrade head; do
    if [ "$attempt" -ge "$MIGRATION_RETRY_ATTEMPTS" ]; then
        echo "数据库迁移失败，已重试 ${attempt} 次" >&2
        exit 1
    fi
    echo "数据库尚未可用，${MIGRATION_RETRY_INTERVAL_SECONDS} 秒后重试（${attempt}/${MIGRATION_RETRY_ATTEMPTS}）" >&2
    attempt=$((attempt + 1))
    sleep "$MIGRATION_RETRY_INTERVAL_SECONDS"
done
echo "数据库迁移完成"

# 启动应用
exec python run.py
