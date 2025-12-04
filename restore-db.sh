#!/bin/bash

# Database Restore Script for License Manager
# Server: 139.59.92.226
# Restores database from backup file

set -e

echo "========================================="
echo "Database Restore - License Manager"
echo "========================================="
echo "Started at: $(date)"
echo ""

BACKUP_FILE="/home/django/license-manager/lmanagement_backup_latest.dump"
DB_NAME="lmanagement"
DB_USER="lmanagement"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Backup file size: $(ls -lh $BACKUP_FILE | awk '{print $5}')"
echo ""

# Step 1: Stop supervisor services to prevent database access
echo "[1/5] Stopping supervisor services..."
sudo supervisorctl stop license-manager || true
sudo supervisorctl stop license-manager-celery || true
sudo supervisorctl stop license-manager-celery-beat || true
sleep 3
echo "✅ Services stopped"

# Step 2: Terminate active connections
echo "[2/5] Terminating active database connections..."
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
sleep 2
echo "✅ Connections terminated"

# Step 3: Drop and recreate database
echo "[3/5] Recreating database..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
echo "✅ Database recreated"

# Step 4: Restore from backup
echo "[4/5] Restoring database from backup..."
echo "This may take a few minutes..."
sudo -u postgres pg_restore -d $DB_NAME --no-owner --no-acl $BACKUP_FILE 2>&1 | grep -v 'already exists' | head -20 || true
sleep 2
echo "✅ Database restored"

# Step 5: Grant permissions
echo "[5/5] Setting database permissions..."
sudo -u postgres psql -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;"
sudo -u postgres psql -d $DB_NAME -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;"
echo "✅ Permissions set"

# Restart services
echo ""
echo "Restarting supervisor services..."
sudo supervisorctl start license-manager
sleep 3
sudo supervisorctl start license-manager-celery || true
sudo supervisorctl start license-manager-celery-beat || true

echo ""
echo "========================================="
echo "✅ Database Restore Complete!"
echo "========================================="
echo "Completed at: $(date)"
echo ""
echo "Service Status:"
sudo supervisorctl status | grep license-manager
echo ""
echo "Verify the application:"
echo "  curl http://localhost:8000"
echo ""
