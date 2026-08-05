#!/usr/bin/env bash
set -Eeuo pipefail

if [ "${PG_BACKUP_ENABLED:-false}" = "true" ]; then
    /usr/local/bin/generate-pgbackrest-config
    chown -R postgres:postgres \
        /etc/pgbackrest \
        "${PG_BACKUP_LOCAL_PATH:-/var/lib/pgbackrest}" \
        "${PG_BACKUP_STATUS_DIR:-/var/lib/postgres-backup-status}"
    stanza="${PG_BACKUP_STANZA:-${POSTGRES_DB:-template}}"
    set -- "$@" \
        -c archive_mode=on \
        -c wal_level=replica \
        -c archive_timeout=300 \
        -c "archive_command=pgbackrest --stanza=${stanza} archive-push %p"
fi

exec /usr/local/bin/docker-entrypoint.sh "$@"
