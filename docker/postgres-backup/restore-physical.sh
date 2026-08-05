#!/usr/bin/env bash
set -Eeuo pipefail

target_dir="${1:-}"
target_time="${2:-}"
stanza="${PG_BACKUP_STANZA:-${POSTGRES_DB:-template}}"

if [ -z "$target_dir" ] || [ -z "$target_time" ]; then
    echo "usage: postgres-backup-restore-physical TARGET_DIRECTORY TARGET_TIME_UTC" >&2
    exit 2
fi

if [ -e "$target_dir" ] && [ -n "$(find "$target_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo "restore target must be empty: $target_dir" >&2
    exit 2
fi

mkdir -p "$target_dir"
exec pgbackrest --stanza="$stanza" --pg1-path="$target_dir" --archive-mode=off \
    --type=time --target="$target_time" restore
