#!/usr/bin/env bash
set -Eeuo pipefail

status_dir="${PG_BACKUP_STATUS_DIR:-/var/lib/postgres-backup-status}"
enabled="${PG_BACKUP_ENABLED:-false}"

if [ "$enabled" = "false" ]; then
    exit 0
fi

now="$(date -u +%s)"

is_fresh() {
    local name="$1"
    local max_age="$2"
    local value
    local age

    [ -f "$status_dir/$name" ] || return 1
    value="$(cat "$status_dir/$name")"
    case "$value" in
        *[!0-9]*|'') return 1 ;;
    esac
    age=$((now - value))
    [ "$age" -ge 0 ] && [ "$age" -le "$max_age" ]
}

is_fresh_or_in_grace_period() {
    local name="$1"
    local max_age="$2"
    local started="$status_dir/started"

    if is_fresh "$name" "$max_age"; then
        return 0
    fi
    [ -f "$status_dir/$name" ] && return 1
    is_fresh "started" "$max_age"
}

is_failed_since_success() {
    local job="$1"
    local failure="$status_dir/last-${job}-failure"
    local success="$status_dir/last-${job}"

    [ -f "$failure" ] || return 1
    [ -f "$success" ] || return 0
    [ "$(cat "$failure")" -gt "$(cat "$success")" ]
}

for requirement in \
    'check 600' \
    'physical 93600' \
    'full 691200' \
    'monthly 3456000' \
    'restore 3456000'; do
    set -- $requirement
    if ! is_fresh_or_in_grace_period "last-$1" "$2"; then
        echo "postgres backup is unhealthy: $1 status is missing or stale" >&2
        exit 1
    fi
    if is_failed_since_success "$1"; then
        echo "postgres backup is unhealthy: latest $1 job failed" >&2
        exit 1
    fi
done

if [ "$(cat "$status_dir/repository-mode" 2>/dev/null || true)" = "local" ]; then
    echo "postgres backup is degraded: repository is local, not off-host S3" >&2
    exit 1
fi
