#!/bin/bash

# Database Management Tools
# Unified script for database backup, restore, and sync operations

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REMOTE_SERVER="django@143.110.252.201"
REMOTE_DB_NAME="lmanagement"
REMOTE_DB_USER="lmanagement"
REMOTE_DB_PASS="lmanagement"
LOCAL_DB_NAME="lmanagement"
LOCAL_DB_USER="lmanagement"
LOCAL_DB_PASS="lmanagement"
BACKUP_DIR="./backups"

print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

show_usage() {
    echo "Database Management Tools"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  backup          Create backup of remote database"
    echo "  download        Download database from remote server to local"
    echo "  restore <file>  Restore local database from backup file"
    echo "  sync            Download and restore remote DB to local (combines download + restore)"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 download"
    echo "  $0 restore backups/backup_20241225.sql"
    echo "  $0 sync"
    echo ""
}

# Function: Create backup on remote server
backup_remote_db() {
    print_header "📦 Creating Remote Database Backup"

    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"

    print_info "Creating backup on remote server..."
    ssh $REMOTE_SERVER "PGPASSWORD='$REMOTE_DB_PASS' pg_dump -U $REMOTE_DB_USER -d $REMOTE_DB_NAME -F p" > "$BACKUP_DIR/$BACKUP_FILE"

    if [ $? -eq 0 ]; then
        print_success "Backup created: $BACKUP_DIR/$BACKUP_FILE"
        local size=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
        print_info "Backup size: $size"
    else
        print_error "Failed to create backup"
        exit 1
    fi
}

# Function: Download database from remote
download_db() {
    print_header "⬇️  Downloading Database from Remote Server"

    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"

    BACKUP_FILE="remote_db_backup_$(date +%Y%m%d_%H%M%S).sql"

    print_info "Server: $REMOTE_SERVER"
    print_info "Database: $REMOTE_DB_NAME"
    print_info "Backup file: $BACKUP_DIR/$BACKUP_FILE"
    echo ""

    # Create backup on remote server
    print_info "Creating database backup on remote server..."
    ssh $REMOTE_SERVER "PGPASSWORD='$REMOTE_DB_PASS' pg_dump -U $REMOTE_DB_USER -d $REMOTE_DB_NAME -F p -f /tmp/$BACKUP_FILE"

    if [ $? -ne 0 ]; then
        print_error "Failed to create backup on remote server"
        exit 1
    fi
    print_success "Backup created on remote server"

    # Download backup file
    print_info "Downloading backup file..."
    scp $REMOTE_SERVER:/tmp/$BACKUP_FILE "$BACKUP_DIR/$BACKUP_FILE"

    if [ $? -ne 0 ]; then
        print_error "Failed to download backup file"
        exit 1
    fi
    print_success "Backup downloaded: $BACKUP_DIR/$BACKUP_FILE"

    # Clean up remote backup
    print_info "Cleaning up remote backup file..."
    ssh $REMOTE_SERVER "rm /tmp/$BACKUP_FILE"
    print_success "Remote cleanup complete"

    # Show file info
    local size=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    print_info "Downloaded backup size: $size"

    echo ""
    print_success "Database downloaded successfully!"
    echo ""
    print_info "To restore this backup, run:"
    echo "  $0 restore $BACKUP_DIR/$BACKUP_FILE"
    echo ""
}

# Function: Restore database from backup file
restore_db() {
    local BACKUP_FILE=$1

    if [ -z "$BACKUP_FILE" ]; then
        print_error "Please specify a backup file to restore"
        echo "Usage: $0 restore <backup-file>"
        exit 1
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        print_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    print_header "🔄 Restoring Database from Backup"

    print_info "Backup file: $BACKUP_FILE"
    print_info "Target database: $LOCAL_DB_NAME"
    echo ""

    # Warning
    echo -e "${RED}⚠️  WARNING: This will DELETE all data in the local database '$LOCAL_DB_NAME'${NC}"
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Operation cancelled"
        exit 0
    fi

    # Stop local Django server if running
    print_info "Stopping local Django server (if running)..."
    pkill -f "python.*manage.py runserver" 2>/dev/null || true
    print_success "Server stopped"

    # Drop and recreate database
    print_info "Dropping existing database..."
    psql -U hardiksottany -d postgres -c "DROP DATABASE IF EXISTS $LOCAL_DB_NAME;" 2>/dev/null

    print_info "Creating new database..."
    psql -U hardiksottany -d postgres -c "CREATE DATABASE $LOCAL_DB_NAME OWNER $LOCAL_DB_USER;" 2>/dev/null

    if [ $? -ne 0 ]; then
        print_error "Failed to recreate database"
        exit 1
    fi
    print_success "Database recreated"

    # Restore backup
    print_info "Restoring backup to local database..."
    PGPASSWORD="$LOCAL_DB_PASS" psql -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -f "$BACKUP_FILE" > /dev/null 2>&1

    if [ $? -ne 0 ]; then
        print_error "Failed to restore backup"
        exit 1
    fi
    print_success "Backup restored successfully"

    # Run migrations
    print_info "Running Django migrations..."
    cd backend
    python manage.py migrate --noinput > /dev/null 2>&1
    cd ..
    print_success "Migrations complete"

    echo ""
    print_success "Database restore completed successfully!"
    echo ""
}

# Function: Sync database (download + restore in one command)
sync_db() {
    print_header "🔄 Syncing Database from Remote to Local"

    # Download
    BACKUP_FILE="remote_db_backup_$(date +%Y%m%d_%H%M%S).sql"
    mkdir -p "$BACKUP_DIR"

    print_info "Step 1/3: Creating backup on remote server..."
    ssh $REMOTE_SERVER "PGPASSWORD='$REMOTE_DB_PASS' pg_dump -U $REMOTE_DB_USER -d $REMOTE_DB_NAME -F c -Z 6 -f /tmp/$BACKUP_FILE"

    if [ $? -ne 0 ]; then
        print_error "Failed to create backup on remote server"
        exit 1
    fi
    print_success "Remote backup created"

    print_info "Step 2/3: Downloading database..."
    scp -C $REMOTE_SERVER:/tmp/$BACKUP_FILE "$BACKUP_DIR/$BACKUP_FILE"

    if [ $? -ne 0 ]; then
        print_error "Failed to download backup"
        ssh $REMOTE_SERVER "rm /tmp/$BACKUP_FILE" 2>/dev/null
        exit 1
    fi

    local size=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    print_success "Downloaded $size to $BACKUP_DIR/$BACKUP_FILE"

    ssh $REMOTE_SERVER "rm /tmp/$BACKUP_FILE"

    echo ""
    print_info "Step 3/3: Restoring to local database..."

    # Warning
    echo -e "${RED}⚠️  This will DELETE all local data${NC}"
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Operation cancelled (backup saved)"
        exit 0
    fi

    # Restore
    print_info "Stopping Django server..."
    pkill -f "python.*manage.py runserver" 2>/dev/null || true

    print_info "Recreating database..."
    psql -U hardiksottany -d postgres -c "DROP DATABASE IF EXISTS $LOCAL_DB_NAME;" 2>/dev/null
    psql -U hardiksottany -d postgres -c "CREATE DATABASE $LOCAL_DB_NAME OWNER $LOCAL_DB_USER;" 2>/dev/null

    if [ $? -ne 0 ]; then
        print_error "Failed to recreate database"
        exit 1
    fi

    print_info "Restoring backup (this may take a while)..."
    PGPASSWORD="$LOCAL_DB_PASS" pg_restore -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -j 4 --no-owner --no-acl "$BACKUP_DIR/$BACKUP_FILE" 2>/dev/null

    if [ $? -ne 0 ]; then
        print_error "Failed to restore backup"
        exit 1
    fi
    print_success "Database restored"

    print_info "Running migrations..."
    cd backend
    python manage.py migrate --noinput > /dev/null 2>&1
    cd ..
    print_success "Migrations complete"

    print_info "Syncing media files..."
    rsync -avz --delete $REMOTE_SERVER:/home/django/license-manager/backend/media/ ./backend/media/

    if [ $? -eq 0 ]; then
        print_success "Media files synced"
    else
        print_error "Failed to sync media files"
    fi

    echo ""
    print_success "Database synced successfully!"
    echo ""
    print_info "Backup saved: $BACKUP_DIR/$BACKUP_FILE"
    echo ""
}

# Main script
if [ $# -eq 0 ]; then
    show_usage
    exit 0
fi

COMMAND=$1

case $COMMAND in
    backup)
        mkdir -p "$BACKUP_DIR"
        backup_remote_db
        ;;
    download)
        download_db
        ;;
    restore)
        restore_db $2
        ;;
    sync)
        sync_db
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo ""
        show_usage
        exit 1
        ;;
esac
