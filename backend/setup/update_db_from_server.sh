#!/bin/bash

# ─── Configuration ─────────────────────────────────────────────
REMOTE_USER="django"
REMOTE_HOST="143.244.139.121"
REMOTE_DB_NAME="lmanagement"
REMOTE_DB_USER="lmanagement"
REMOTE_DB_PASSWORD="lmanagement"
REMOTE_BACKUP_PATH="/home/django/lmanagement.backup"

LOCAL_DB_NAME="lmanagement"
LOCAL_DB_USER="lmanagement"
LOCAL_DB_PASSWORD="lmanagement"
SUPERUSER="postgres"
SUPERUSER_PASSWORD="postgres_password"
LOCAL_PORT="5432"

BACKUP_FILE="lmanagement.backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOGFILE="db_update_$TIMESTAMP.log"

# ─── Step 1: Trigger pg_dump on remote ─────────────────────────
echo "🔄 Starting remote dump..." | tee -a $LOGFILE
ssh ${REMOTE_USER}@${REMOTE_HOST} "PGPASSWORD=${REMOTE_DB_PASSWORD} pg_dump -U ${REMOTE_DB_USER} -h localhost -p ${LOCAL_PORT} -F c -b -v -f ${REMOTE_BACKUP_PATH} ${REMOTE_DB_NAME}" 2>&1 | tee -a $LOGFILE

# ─── Step 2: Copy backup file to local ─────────────────────────
echo "📥 Copying backup to local..." | tee -a $LOGFILE
scp ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BACKUP_PATH} ./ 2>&1 | tee -a $LOGFILE

# ─── Step 3: Drop and recreate local database ──────────────────
echo "💣 Dropping and recreating local database..." | tee -a $LOGFILE
PGPASSWORD=${SUPERUSER_PASSWORD} dropdb -U ${SUPERUSER} -h localhost -p ${LOCAL_PORT} --if-exists ${LOCAL_DB_NAME}
PGPASSWORD=${SUPERUSER_PASSWORD} createdb -U ${SUPERUSER} -h localhost -p ${LOCAL_PORT} -O ${LOCAL_DB_USER} ${LOCAL_DB_NAME}

# ─── Step 4: Restore backup locally ────────────────────────────
echo "♻️ Restoring database locally..." | tee -a $LOGFILE
PGPASSWORD=${LOCAL_DB_PASSWORD} pg_restore -U ${LOCAL_DB_USER} -h localhost -p ${LOCAL_PORT} -d ${LOCAL_DB_NAME} -v ${BACKUP_FILE} 2>&1 | tee -a $LOGFILE

# ─── Step 5: Delete backup file ────────────────────────────────
echo "🗑 Deleting backup file..." | tee -a $LOGFILE
rm -f ${BACKUP_FILE}

echo "✅ Database update complete. Log saved to $LOGFILE"
