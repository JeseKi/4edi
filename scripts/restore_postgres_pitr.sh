#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/restore_postgres_pitr.sh TARGET_DIRECTORY TARGET_TIME_UTC

Restore a pgBackRest physical backup to an empty host directory. The script does
not start the recovered instance and never writes to postgres-data.
EOF
}

if [ "${1:-}" = "--help" ] || [ "$#" -ne 2 ]; then
    usage
    [ "${1:-}" = "--help" ] && exit 0
    exit 2
fi

target_dir="$1"
target_time="$2"

if [ -e "$target_dir" ] && [ -n "$(find "$target_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo "restore target must be an empty directory: $target_dir" >&2
    exit 2
fi

mkdir -p "$target_dir"
target_dir="$(cd "$target_dir" && pwd -P)"

docker compose -f docker-compose.yml -f docker-compose.postgres.yml run --rm --no-deps \
    --user root \
    -v "$target_dir:/restore-data" \
    postgres-backup /usr/local/bin/postgres-backup-restore-physical \
    /restore-data "$target_time"
