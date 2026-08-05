#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/restore_postgres_monthly.sh SNAPSHOT AGE_IDENTITY TARGET_DATABASE

Restore an encrypted monthly pg_dump archive into a newly named database on the
Compose PostgreSQL instance. TARGET_DATABASE must differ from POSTGRES_DB.
EOF
}

if [ "${1:-}" = "--help" ] || [ "$#" -ne 3 ]; then
    usage
    [ "${1:-}" = "--help" ] && exit 0
    exit 2
fi

snapshot="$1"
identity="$2"
target_database="$3"

for path in "$snapshot" "$identity"; do
    if [ ! -f "$path" ]; then
        echo "file not found: $path" >&2
        exit 2
    fi
done

snapshot="$(cd "$(dirname "$snapshot")" && pwd -P)/$(basename "$snapshot")"
identity="$(cd "$(dirname "$identity")" && pwd -P)/$(basename "$identity")"

docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
    --user root \
    -v "$snapshot:/restore/monthly.dump.age:ro" \
    -v "$identity:/restore/age-identity.txt:ro" \
    postgres-backup /usr/local/bin/postgres-backup-restore-monthly \
    /restore/monthly.dump.age /restore/age-identity.txt "$target_database"
