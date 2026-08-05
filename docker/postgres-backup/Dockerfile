FROM postgres:17-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && sed -i 's#http://apt.postgresql.org#https://apt.postgresql.org#' /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        age \
        pgbackrest \
        python3 \
        python3-boto3 \
        util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /etc/pgbackrest /var/lib/pgbackrest /var/lib/postgres-backup-status \
    && chown -R postgres:postgres /etc/pgbackrest /var/lib/pgbackrest /var/lib/postgres-backup-status

COPY docker/postgres-backup/generate-pgbackrest-config.sh /usr/local/bin/generate-pgbackrest-config
COPY docker/postgres-backup/postgres-entrypoint.sh /usr/local/bin/postgres-backup-postgres-entrypoint
COPY docker/postgres-backup/backup-entrypoint.sh /usr/local/bin/postgres-backup-entrypoint
COPY docker/postgres-backup/backup-runner.sh /usr/local/bin/postgres-backup-runner
COPY docker/postgres-backup/backup-healthcheck.sh /usr/local/bin/postgres-backup-healthcheck
COPY docker/postgres-backup/restore-physical.sh /usr/local/bin/postgres-backup-restore-physical
COPY docker/postgres-backup/restore-monthly.sh /usr/local/bin/postgres-backup-restore-monthly
COPY docker/postgres-backup/upload-monthly.py /usr/local/bin/postgres-backup-upload-monthly

RUN chmod +x /usr/local/bin/generate-pgbackrest-config \
        /usr/local/bin/postgres-backup-postgres-entrypoint \
        /usr/local/bin/postgres-backup-entrypoint \
        /usr/local/bin/postgres-backup-runner \
        /usr/local/bin/postgres-backup-healthcheck \
        /usr/local/bin/postgres-backup-restore-physical \
        /usr/local/bin/postgres-backup-restore-monthly \
        /usr/local/bin/postgres-backup-upload-monthly
