#!/usr/bin/env bash
set -Eeuo pipefail

snapshot="${1:-}"
identity_file="${2:-}"
target_database="${3:-}"
source_database="${POSTGRES_DB:-template}"
database_user="${POSTGRES_USER:-template}"

if [ -z "$snapshot" ] || [ -z "$identity_file" ] || [ -z "$target_database" ]; then
    echo "usage: postgres-backup-restore-monthly SNAPSHOT AGE_IDENTITY TARGET_DATABASE" >&2
    exit 2
fi
if [ "$target_database" = "$source_database" ]; then
    echo "monthly restore target must not be the production database" >&2
    exit 2
fi
case "$target_database" in
    *[!A-Za-z0-9_]*|'')
        echo "monthly restore target may only contain letters, numbers, and _" >&2
        exit 2
        ;;
esac

export PGPASSWORD="${POSTGRES_PASSWORD:-}"
export PGHOST="/var/run/postgresql"
export PGPORT="5432"

if ! psql -U "$database_user" -d postgres -Atqc \
    "SELECT 1 FROM pg_database WHERE datname = '$target_database'" | grep -qx 1; then
    createdb -U "$database_user" "$target_database"
fi

age --decrypt --identity "$identity_file" "$snapshot" \
    | pg_restore --no-owner --clean --if-exists --exit-on-error \
        --username="$database_user" --dbname="$target_database"
