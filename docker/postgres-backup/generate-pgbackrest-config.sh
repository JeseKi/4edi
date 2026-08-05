#!/usr/bin/env bash
set -Eeuo pipefail

config_path="${PGBACKREST_CONFIG_PATH:-/etc/pgbackrest/pgbackrest.conf}"
status_dir="${PG_BACKUP_STATUS_DIR:-/var/lib/postgres-backup-status}"
local_path="${PG_BACKUP_LOCAL_PATH:-/var/lib/pgbackrest}"
enabled="${PG_BACKUP_ENABLED:-false}"
requested_mode="${PG_BACKUP_MODE:-auto}"
stanza="${PG_BACKUP_STANZA:-${POSTGRES_DB:-template}}"

die() {
    echo "postgres backup configuration error: $*" >&2
    exit 1
}

case "$enabled" in
    true|false) ;;
    *) die "PG_BACKUP_ENABLED must be true or false" ;;
esac

mkdir -p "$(dirname "$config_path")" "$status_dir"

if [ "$enabled" = "false" ]; then
    rm -f "$config_path"
    printf '%s\n' disabled > "$status_dir/repository-mode"
    exit 0
fi

case "$requested_mode" in
    auto|s3|local) ;;
    *) die "PG_BACKUP_MODE must be auto, s3, or local" ;;
esac

case "$stanza" in
    *[!A-Za-z0-9_-]*|'') die "PG_BACKUP_STANZA may only contain letters, numbers, _ and -" ;;
esac

repo_cipher_pass="${PG_BACKUP_REPO_CIPHER_PASS:-}"
age_recipient="${PG_BACKUP_AGE_RECIPIENT:-}"
[ -n "$repo_cipher_pass" ] || die "PG_BACKUP_REPO_CIPHER_PASS is required when backups are enabled"
[ -n "$age_recipient" ] || die "PG_BACKUP_AGE_RECIPIENT is required when backups are enabled"

s3_bucket="${PG_BACKUP_S3_BUCKET:-}"
s3_endpoint="${PG_BACKUP_S3_ENDPOINT:-}"
s3_port="${PG_BACKUP_S3_PORT:-443}"
s3_access_key="${PG_BACKUP_S3_ACCESS_KEY_ID:-}"
s3_secret_key="${PG_BACKUP_S3_SECRET_ACCESS_KEY:-}"
s3_values=0
for value in "$s3_bucket" "$s3_endpoint" "$s3_access_key" "$s3_secret_key"; do
    if [ -n "$value" ]; then
        s3_values=$((s3_values + 1))
    fi
done

if [ "$requested_mode" = "auto" ]; then
    if [ "$s3_values" = 0 ]; then
        resolved_mode=local
    elif [ "$s3_values" = 4 ]; then
        resolved_mode=s3
    else
        die "S3 backup settings are incomplete; set all S3 settings or none of them"
    fi
else
    resolved_mode="$requested_mode"
fi

if [ "$resolved_mode" = "s3" ] && [ "$s3_values" != 4 ]; then
    die "PG_BACKUP_MODE=s3 requires bucket, endpoint, access key, and secret access key"
fi
if [ "$resolved_mode" = "s3" ]; then
    case "$s3_endpoint" in
        *://*|*/*|'') die "PG_BACKUP_S3_ENDPOINT must be a host name without a URL scheme or path" ;;
    esac
    case "$s3_port" in
        *[!0-9]*|'') die "PG_BACKUP_S3_PORT must be numeric" ;;
    esac
    case "${PG_BACKUP_S3_VERIFY_TLS:-y}" in
        y|n) ;;
        *) die "PG_BACKUP_S3_VERIFY_TLS must be y or n" ;;
    esac
fi

repo_path="${PG_BACKUP_S3_PREFIX:-/${POSTGRES_DB:-template}}"
case "$repo_path" in
    /*) ;;
    *) repo_path="/$repo_path" ;;
esac

umask 077
cat > "$config_path" <<EOF
[${stanza}]
pg1-path=/var/lib/postgresql/data
pg1-socket-path=/var/run/postgresql
pg1-port=5432
pg1-user=${POSTGRES_USER:-postgres}

[global]
archive-async=n
compress-type=gz
log-level-console=info
log-level-file=off
lock-path=/tmp/pgbackrest-lock
process-max=2
repo1-cipher-pass=${repo_cipher_pass}
repo1-cipher-type=aes-256-cbc
repo1-retention-archive=5
repo1-retention-archive-type=full
repo1-retention-diff=6
repo1-retention-full=5
EOF

if [ "$resolved_mode" = "s3" ]; then
    cat >> "$config_path" <<EOF
repo1-bundle=y
repo1-path=${repo_path}/pgbackrest
repo1-s3-bucket=${s3_bucket}
repo1-s3-endpoint=${s3_endpoint}
repo1-s3-key=${s3_access_key}
repo1-s3-key-secret=${s3_secret_key}
repo1-s3-region=${PG_BACKUP_S3_REGION:-us-east-1}
repo1-s3-uri-style=${PG_BACKUP_S3_URI_STYLE:-path}
repo1-storage-port=${s3_port}
repo1-storage-verify-tls=${PG_BACKUP_S3_VERIFY_TLS:-y}
repo1-type=s3
EOF
else
    mkdir -p "$local_path"
    cat >> "$config_path" <<EOF
repo1-path=${local_path}
repo1-type=posix
EOF
fi

previous_mode="$(cat "$status_dir/repository-mode" 2>/dev/null || true)"
if [ -n "$previous_mode" ] && [ "$previous_mode" != "$resolved_mode" ]; then
    echo "postgres backup: repository changed from ${previous_mode} to ${resolved_mode}; resetting runtime status"
    rm -f "$status_dir"/last-* "$status_dir"/started
fi
printf '%s\n' "$resolved_mode" > "$status_dir/repository-mode"
