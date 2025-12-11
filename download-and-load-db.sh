#!/bin/bash

# Script to download database from remote server and load it locally

SERVER_IP="143.110.252.201"
SERVER_USER="django"
REMOTE_DB_NAME="lmanagement"
REMOTE_DB_USER="lmanagement"
REMOTE_DB_PASS="lmanagement"
LOCAL_DB_NAME="lmanagement"
LOCAL_DB_USER="lmanagement"
LOCAL_DB_PASS="lmanagement"
BACKUP_FILE="remote_db_backup_$(date +%Y%m%d_%H%M%S).sql"

echo "=========================================="
echo "Database Download and Load Script"
echo "=========================================="
echo "Server: $SERVER_USER@$SERVER_IP"
echo "Remote DB: $REMOTE_DB_NAME"
echo "Local DB: $LOCAL_DB_NAME"
echo "Backup file: $BACKUP_FILE"
echo "=========================================="
echo ""

# Step 1: Create backup on remote server
echo "Step 1: Creating database backup on remote server..."
ssh $SERVER_USER@$SERVER_IP "PGPASSWORD='$REMOTE_DB_PASS' pg_dump -U $REMOTE_DB_USER -d $REMOTE_DB_NAME -F p -f /tmp/$BACKUP_FILE"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create backup on remote server"
    exit 1
fi
echo "✓ Backup created successfully on remote server"
echo ""

# Step 2: Download backup file to local machine
echo "Step 2: Downloading backup file from remote server..."
scp $SERVER_USER@$SERVER_IP:/tmp/$BACKUP_FILE ./$BACKUP_FILE

if [ $? -ne 0 ]; then
    echo "Error: Failed to download backup file"
    exit 1
fi
echo "✓ Backup file downloaded successfully"
echo ""

# Step 3: Clean up remote backup file
echo "Step 3: Cleaning up remote backup file..."
ssh $SERVER_USER@$SERVER_IP "rm /tmp/$BACKUP_FILE"
echo "✓ Remote backup file cleaned up"
echo ""

# Step 4: Stop local Django development server (if running)
echo "Step 4: Checking for running Django server..."
pkill -f "python.*manage.py runserver" 2>/dev/null
echo "✓ Local Django server stopped (if it was running)"
echo ""

# Step 5: Drop and recreate local database
echo "Step 5: Dropping and recreating local database..."
echo "WARNING: This will delete all data in the local database '$LOCAL_DB_NAME'"
read -p "Continue? (y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Operation cancelled"
    exit 0
fi

# Drop existing database (use hardiksottany superuser)
psql -U hardiksottany -d postgres -c "DROP DATABASE IF EXISTS $LOCAL_DB_NAME;"

if [ $? -ne 0 ]; then
    echo "Error: Failed to drop local database"
    exit 1
fi

# Create new database (use hardiksottany superuser)
psql -U hardiksottany -d postgres -c "CREATE DATABASE $LOCAL_DB_NAME OWNER $LOCAL_DB_USER;"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create local database"
    exit 1
fi
echo "✓ Local database recreated successfully"
echo ""

# Step 6: Restore backup to local database
echo "Step 6: Restoring backup to local database..."
PGPASSWORD="$LOCAL_DB_PASS" psql -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -f ./$BACKUP_FILE

if [ $? -ne 0 ]; then
    echo "Error: Failed to restore backup to local database"
    exit 1
fi
echo "✓ Backup restored successfully to local database"
echo ""

# Step 7: Run migrations (if needed)
echo "Step 7: Running Django migrations..."
cd backend
python manage.py migrate --noinput
cd ..
echo "✓ Migrations completed"
echo ""

echo "=========================================="
echo "Database download and load completed!"
echo "=========================================="
echo ""
echo "Backup file saved as: $BACKUP_FILE"
echo "You can delete this file if no longer needed:"
echo "  rm $BACKUP_FILE"
echo ""
