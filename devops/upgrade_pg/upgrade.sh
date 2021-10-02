docker stop lms_db_1

# Put values here if you've configured them before
CURRENT_VERSION=11
NEW_VERSION=14
DB_NAME=lms
DB_USERNAME=lmsweb
DB_PASSWORD=

echo "Remove these two lines to indicate you have filled the details"
return 1

CURRENT_DATE=$(date +%d-%m-%Y_%H_%M_%S)
MOUNT_PATH=/pg_data
PG_OLD_DATA=/pg_data/${CURRENT_VERSION}/data
PG_NEW_DATA=/pg_data/${NEW_VERSION}/data
BACKUP_FILENAME=v${CURRENT_VERSION}.${CURRENT_DATE}.sql
BACKUP_PATH=$MOUNT_PATH/backup/$BACKUP_FILENAME
BACKUP_DIR=$(dirname "$BACKUP_PATH")
VOLUME_NAME=lms_db-data-volume

# Step 1: Create a backup
docker run --rm -v $VOLUME_NAME:$MOUNT_PATH \
       -e PGDATA=$PG_OLD_DATA \
       -e POSTGRES_DB="${DB_NAME:-db}" \
       -e POSTGRES_USER="${DB_USERNAME:-postgres}" \
       -e POSTGRES_PASSWORD="${DB_PASSWORD:-postgres}" \
       postgres:${CURRENT_VERSION}-alpine \
       /bin/bash -c "chown -R postgres:postgres $MOUNT_PATH \
                && su - postgres /bin/bash -c \"/usr/local/bin/pg_ctl -D \\\"\$PGDATA\\\" start\" \
                && mkdir -p \"$BACKUP_DIR\" \
                && pg_dumpall -U $DB_USERNAME -f \"$BACKUP_PATH\" \
                && chown postgres:postgres \"$BACKUP_PATH\""

# Step 2: Create a new database from the backup
docker run --rm -v $VOLUME_NAME:$MOUNT_PATH \
       -e PGDATA=$PG_NEW_DATA \
       -e POSTGRES_DB="${DB_NAME:-db}" \
       -e POSTGRES_USER="${DB_USERNAME:-postgres}" \
       -e POSTGRES_PASSWORD="${DB_PASSWORD:-postgres}" \
       postgres:$NEW_VERSION-alpine \
       /bin/bash -c "ls -la \"$BACKUP_DIR\" \
                && mkdir -p \"\$PGDATA\" \
                && chown -R postgres:postgres \"\$PGDATA\" \
                && rm -rf $PG_NEW_DATA/* \
                && su - postgres -c \"initdb -D \\\"\$PGDATA\\\"\" \
                && su - postgres -c \"pg_ctl -D \\\"\$PGDATA\\\" -l logfile start\" \
                && su - postgres -c \"psql -f $BACKUP_PATH\" \
                && printf \"\\\nhost all all all md5\\\n\" >> \"\$PGDATA/pg_hba.conf\" \
                "
echo "Upgrade finished. Check for bad log messages. If none found, rerun:"
echo "source ./build.sh && source ./start.sh && source ./bootstrap.sh"
