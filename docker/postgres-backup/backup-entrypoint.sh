#!/usr/bin/env bash
set -Eeuo pipefail

/usr/local/bin/generate-pgbackrest-config
if [ "$(id -u)" = 0 ]; then
    chown -R postgres:postgres \
        /etc/pgbackrest \
        "${PG_BACKUP_LOCAL_PATH:-/var/lib/pgbackrest}" \
        "${PG_BACKUP_STATUS_DIR:-/var/lib/postgres-backup-status}"
fi
exec "$@"
