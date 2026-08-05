#!/usr/bin/env bash
set -Eeuo pipefail

status_dir="${PG_BACKUP_STATUS_DIR:-/var/lib/postgres-backup-status}"
local_path="${PG_BACKUP_LOCAL_PATH:-/var/lib/pgbackrest}"
stanza="${PG_BACKUP_STANZA:-${POSTGRES_DB:-template}}"
database_name="${POSTGRES_DB:-template}"
database_user="${POSTGRES_USER:-template}"
enabled="${PG_BACKUP_ENABLED:-false}"
lock_file="$status_dir/runner.lock"

mkdir -p "$status_dir" "$status_dir/work"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
export PGHOST="/var/run/postgresql"
export PGPORT="5432"

timestamp() {
    date -u +%s
}

record_success() {
    local job="$1"
    timestamp > "$status_dir/last-${job}"
    rm -f "$status_dir/last-${job}-failure"
}

record_failure() {
    local job="$1"
    timestamp > "$status_dir/last-${job}-failure"
}

is_fresh() {
    local job="$1"
    local max_age="$2"
    local path="$status_dir/last-${job}"
    local value

    [ -f "$path" ] || return 1
    value="$(cat "$path")"
    case "$value" in
        *[!0-9]*|'') return 1 ;;
    esac
    [ $(( $(timestamp) - value )) -le "$max_age" ]
}

pgbackrest() {
    command pgbackrest --stanza="$stanza" --log-level-console=info "$@"
}

run_job() {
    local job="$1"
    local result
    shift

    if (
        flock -n 9 || exit 75
        echo "postgres backup: start ${job}"
        if "$@"; then
            record_success "$job"
            echo "postgres backup: completed ${job}"
            exit 0
        fi
        record_failure "$job"
        echo "postgres backup: failed ${job}" >&2
        exit 1
    ) 9>"$lock_file"; then
        return 0
    fi
    result=$?
    if [ "$result" = 75 ]; then
        echo "postgres backup: skip ${job}; another job is running"
        return 0
    fi
    return 1
}

create_stanza() {
    pgbackrest stanza-create
}

run_check() {
    pgbackrest check
}

run_full_backup() {
    pgbackrest --type=full backup
    record_success physical
}

run_diff_backup() {
    pgbackrest --type=diff backup
    record_success physical
}

monthly_prefix() {
    local prefix="${PG_BACKUP_S3_PREFIX:-/$database_name}"
    prefix="${prefix#/}"
    printf '%s/monthly' "${prefix%/}"
}

prune_local_monthly() {
    local directory="$1"
    local files=()
    local file

    shopt -s nullglob
    files=("$directory"/*.dump.age)
    shopt -u nullglob
    if [ "${#files[@]}" -le 12 ]; then
        return 0
    fi
    IFS=$'\n' files=( $(printf '%s\n' "${files[@]}" | sort -r) )
    unset IFS
    for file in "${files[@]:12}"; do
        rm -f "$file"
    done
}

run_monthly_snapshot() {
    local mode
    local destination_dir
    local filename
    local final_path
    local temp_path
    local key

    mode="$(cat "$status_dir/repository-mode")"
    filename="${database_name}-$(date -u +%Y-%m-%dT%H%M%SZ).dump.age"
    if [ "$mode" = "local" ]; then
        destination_dir="$local_path/monthly"
    else
        destination_dir="$status_dir/work/monthly"
    fi
    mkdir -p "$destination_dir"
    final_path="$destination_dir/$filename"
    temp_path="${final_path}.partial"

    if ! pg_dump --format=custom --no-owner --username="$database_user" --dbname="$database_name" \
        | age --recipient "${PG_BACKUP_AGE_RECIPIENT}" --output "$temp_path"; then
        rm -f "$temp_path"
        return 1
    fi
    if ! mv "$temp_path" "$final_path"; then
        rm -f "$temp_path"
        return 1
    fi

    if [ "$mode" = "s3" ]; then
        key="$(monthly_prefix)/$filename"
        /usr/local/bin/postgres-backup-upload-monthly --file "$final_path" --key "$key" --retain 12
        rm -f "$final_path"
    else
        prune_local_monthly "$destination_dir"
    fi
}

run_restore_drill() {
    local work_dir
    local data_dir
    local socket_dir
    local log_file
    local postgres_pid
    local ready=false
    local _

    work_dir="$(mktemp -d "$status_dir/work/restore.XXXXXX")"
    data_dir="$work_dir/data"
    socket_dir="$work_dir/socket"
    log_file="$work_dir/postgres.log"
    mkdir -p "$data_dir" "$socket_dir"

    pgbackrest --pg1-path="$data_dir" --archive-mode=off restore
    postgres -D "$data_dir" \
        -c listen_addresses='' \
        -c "unix_socket_directories=$socket_dir" \
        -c port=55432 \
        >"$log_file" 2>&1 &
    postgres_pid=$!

    for _ in $(seq 1 60); do
        if pg_isready -h "$socket_dir" -p 55432 -U "$database_user" -d "$database_name" >/dev/null 2>&1; then
            ready=true
            break
        fi
        sleep 1
    done

    if [ "$ready" != true ]; then
        cat "$log_file" >&2 || true
        kill "$postgres_pid" 2>/dev/null || true
        wait "$postgres_pid" 2>/dev/null || true
        rm -rf "$work_dir"
        return 1
    fi

    if ! psql -h "$socket_dir" -p 55432 -U "$database_user" -d "$database_name" \
        -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null; then
        kill "$postgres_pid" 2>/dev/null || true
        wait "$postgres_pid" 2>/dev/null || true
        rm -rf "$work_dir"
        return 1
    fi

    if psql -h "$socket_dir" -p 55432 -U "$database_user" -d "$database_name" -Atqc \
        "SELECT to_regclass('public.alembic_version')" | grep -qx alembic_version; then
        if ! psql -h "$socket_dir" -p 55432 -U "$database_user" -d "$database_name" \
            -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM alembic_version LIMIT 1' >/dev/null; then
            kill "$postgres_pid" 2>/dev/null || true
            wait "$postgres_pid" 2>/dev/null || true
            rm -rf "$work_dir"
            return 1
        fi
    fi

    kill "$postgres_pid"
    wait "$postgres_pid"
    rm -rf "$work_dir"
}

run_initial_jobs() {
    until pg_isready -U "$database_user" -d "$database_name" >/dev/null 2>&1; do
        echo "postgres backup: waiting for PostgreSQL"
        sleep 2
    done

    until run_job check create_stanza; do
        sleep 10
    done
    until run_job check run_check; do
        sleep 10
    done

    if ! is_fresh full 691200; then
        until run_job full run_full_backup; do
            sleep 30
        done
    elif ! is_fresh physical 93600; then
        until run_job physical run_diff_backup; do
            sleep 30
        done
    fi

    printf '%s\n' "$(timestamp)" > "$status_dir/started"
}

run_scheduled_job_once() {
    local job="$1"
    local slot="$2"
    shift 2
    local marker="$status_dir/last-${job}-slot"

    if [ "$(cat "$marker" 2>/dev/null || true)" = "$slot" ]; then
        return 0
    fi
    printf '%s\n' "$slot" > "$marker"
    run_job "$job" "$@" || true
}

run_daemon() {
    local minute
    local hour
    local weekday
    local day
    local slot

    if [ "$enabled" = "false" ]; then
        echo "postgres backup: disabled"
        while :; do sleep 3600; done
    fi

    run_initial_jobs
    while :; do
        minute="$(date -u +%M)"
        hour="$(date -u +%H)"
        weekday="$(date -u +%u)"
        day="$(date -u +%d)"
        slot="$(date -u +%Y%m%d%H%M)"

        if [ $((10#$minute % 5)) -eq 0 ]; then
            run_scheduled_job_once check "$slot" run_check
        fi
        if [ "$hour" = 02 ] && [ "$minute" = 00 ]; then
            if [ "$weekday" = 7 ]; then
                run_scheduled_job_once full "$slot" run_full_backup
            else
                run_scheduled_job_once physical "$slot" run_diff_backup
            fi
        fi
        if [ "$day" = 01 ] && [ "$hour" = 03 ] && [ "$minute" = 30 ]; then
            run_scheduled_job_once monthly "$slot" run_monthly_snapshot
        fi
        if [ "$day" = 02 ] && [ "$hour" = 03 ] && [ "$minute" = 30 ]; then
            run_scheduled_job_once restore "$slot" run_restore_drill
        fi
        sleep 30
    done
}

case "${1:-daemon}" in
    daemon) run_daemon ;;
    check) run_job check run_check ;;
    full) run_job full run_full_backup ;;
    diff) run_job physical run_diff_backup ;;
    monthly) run_job monthly run_monthly_snapshot ;;
    restore-drill) run_job restore run_restore_drill ;;
    *)
        echo "usage: postgres-backup-runner [daemon|check|full|diff|monthly|restore-drill]" >&2
        exit 2
        ;;
esac
