#!/bin/bash

# Media Sync Tool
# Sync media files between remote server and local machine

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration (override from the environment when needed)
REMOTE_SERVER="${REMOTE_SERVER:-django@143.110.252.201}"
REMOTE_MEDIA_PATH="${REMOTE_MEDIA_PATH:-/home/django/license-manager/backend/media}"
LOCAL_MEDIA_PATH="${LOCAL_MEDIA_PATH:-$PROJECT_ROOT/backend/media}"
RSYNC_BIN="${RSYNC_BIN:-rsync}"
SSH_BIN="${SSH_BIN:-ssh}"

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

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

show_usage() {
    echo "Media Sync Tool"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  download      Download media from remote server to local"
    echo "  upload        Upload media from local to remote server"
    echo "  sync          Two-way sync between local and remote"
    echo "  status        Show media directory sizes"
    echo ""
    echo "Options:"
    echo "  --dry-run     Show what would be transferred without actually doing it"
    echo "  --delete      Delete files in destination that don't exist in source"
    echo ""
    echo "Examples:"
    echo "  $0 download"
    echo "  $0 download --dry-run"
    echo "  $0 upload --delete"
    echo "  $0 status"
    echo ""
}

check_rsync() {
    if ! command -v "$RSYNC_BIN" &> /dev/null; then
        print_error "rsync is not installed"
        echo ""
        echo "Please install rsync:"
        echo "  macOS: brew install rsync"
        echo "  Ubuntu/Debian: sudo apt-get install rsync"
        echo "  RHEL/CentOS: sudo yum install rsync"
        exit 1
    fi
}

validate_config() {
    if [[ -z "$REMOTE_SERVER" || -z "$REMOTE_MEDIA_PATH" || -z "$LOCAL_MEDIA_PATH" ]]; then
        print_error "Remote server and media paths must be configured"
        exit 1
    fi

    if [[ "$REMOTE_MEDIA_PATH" != /* || "$LOCAL_MEDIA_PATH" != /* ]]; then
        print_error "Remote and local media paths must be absolute"
        exit 1
    fi

    if [[ "$REMOTE_MEDIA_PATH" == *"'"* || "$REMOTE_MEDIA_PATH" == *$'\n'* || "$REMOTE_MEDIA_PATH" == *$'\r'* ]]; then
        print_error "Remote media path contains unsupported shell characters"
        exit 1
    fi
}

parse_transfer_options() {
    DRY_RUN_FLAG=""
    DELETE_FLAG=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN_FLAG="--dry-run"
                ;;
            --delete)
                DELETE_FLAG="--delete"
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
        shift
    done
}

check_ssh_connection() {
    validate_config
    print_info "Testing SSH connection to $REMOTE_SERVER..."
    if "$SSH_BIN" -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_SERVER" "echo 'Connection successful'" &> /dev/null; then
        print_success "SSH connection successful"
        return 0
    else
        print_error "Cannot connect to remote server"
        echo ""
        echo "Please ensure:"
        echo "  1. SSH key is set up for $REMOTE_SERVER"
        echo "  2. Server is accessible"
        echo "  3. You have the correct permissions"
        exit 1
    fi
}

get_remote_size() {
    validate_config
    "$SSH_BIN" "$REMOTE_SERVER" "du -sh '$REMOTE_MEDIA_PATH' 2>/dev/null | cut -f1" 2>/dev/null || echo "N/A"
}

get_local_size() {
    if [ -d "$LOCAL_MEDIA_PATH" ]; then
        du -sh "$LOCAL_MEDIA_PATH" 2>/dev/null | cut -f1
    else
        echo "N/A"
    fi
}

download_media() {
    local DRY_RUN_FLAG DELETE_FLAG
    parse_transfer_options "$@"

    print_header "📥 Downloading Media from Remote Server"

    check_rsync
    check_ssh_connection

    print_info "Remote server: $REMOTE_SERVER"
    print_info "Remote path: $REMOTE_MEDIA_PATH"
    print_info "Local path: $LOCAL_MEDIA_PATH"

    if [ -n "$DRY_RUN_FLAG" ]; then
        print_warning "DRY RUN MODE - No files will be transferred"
    fi

    if [ -n "$DELETE_FLAG" ]; then
        print_warning "DELETE MODE - Files in local that don't exist on remote will be deleted"
    fi

    echo ""
    print_info "Starting download..."
    echo ""

    # Create local media directory if it doesn't exist
    mkdir -p "$LOCAL_MEDIA_PATH"

    if ! "$RSYNC_BIN" -avz --progress ${DRY_RUN_FLAG:+"$DRY_RUN_FLAG"} ${DELETE_FLAG:+"$DELETE_FLAG"} \
        "$REMOTE_SERVER:$REMOTE_MEDIA_PATH/" "$LOCAL_MEDIA_PATH/"; then
        echo ""
        print_error "Media download failed"
        exit 1
    fi

    echo ""
    print_success "Media download completed successfully!"
    echo ""
    print_info "Local media size: $(get_local_size)"
}

upload_media() {
    local DRY_RUN_FLAG DELETE_FLAG
    parse_transfer_options "$@"

    print_header "📤 Uploading Media to Remote Server"

    check_rsync
    check_ssh_connection

    # Check if local media exists
    if [ ! -d "$LOCAL_MEDIA_PATH" ]; then
        print_error "Local media directory does not exist: $LOCAL_MEDIA_PATH"
        exit 1
    fi

    print_info "Local path: $LOCAL_MEDIA_PATH"
    print_info "Remote server: $REMOTE_SERVER"
    print_info "Remote path: $REMOTE_MEDIA_PATH"

    if [ -n "$DRY_RUN_FLAG" ]; then
        print_warning "DRY RUN MODE - No files will be transferred"
    fi

    if [ -n "$DELETE_FLAG" ]; then
        print_warning "DELETE MODE - Files on remote that don't exist locally will be deleted"
    fi

    echo ""
    print_warning "This will upload local media to the remote server!"
    read -r -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Operation cancelled"
        exit 0
    fi

    echo ""
    print_info "Starting upload..."
    echo ""

    if ! "$RSYNC_BIN" -avz --progress ${DRY_RUN_FLAG:+"$DRY_RUN_FLAG"} ${DELETE_FLAG:+"$DELETE_FLAG"} \
        "$LOCAL_MEDIA_PATH/" "$REMOTE_SERVER:$REMOTE_MEDIA_PATH/"; then
        echo ""
        print_error "Media upload failed"
        exit 1
    fi

    echo ""
    print_success "Media upload completed successfully!"
    echo ""
    print_info "Remote media size: $(get_remote_size)"
}

sync_media() {
    local DRY_RUN_FLAG=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN_FLAG="--dry-run"
                ;;
            --delete)
                print_error "--delete is not supported for two-way sync"
                exit 1
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
        shift
    done

    print_header "🔄 Two-Way Media Sync"

    check_rsync
    check_ssh_connection

    if [ ! -d "$LOCAL_MEDIA_PATH" ]; then
        print_error "Local media directory does not exist: $LOCAL_MEDIA_PATH"
        exit 1
    fi

    print_warning "This will perform a two-way sync between local and remote"
    print_warning "Newer files will overwrite older files in both directions"
    if [ -n "$DRY_RUN_FLAG" ]; then
        print_warning "DRY RUN MODE - No files will be transferred"
    fi
    echo ""
    read -r -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Operation cancelled"
        exit 0
    fi

    echo ""
    print_info "Syncing local → remote..."
    if ! "$RSYNC_BIN" -avz --progress --update ${DRY_RUN_FLAG:+"$DRY_RUN_FLAG"} \
        "$LOCAL_MEDIA_PATH/" "$REMOTE_SERVER:$REMOTE_MEDIA_PATH/"; then
        print_error "Sync failed while uploading local media"
        exit 1
    fi

    echo ""
    print_info "Syncing remote → local..."
    if ! "$RSYNC_BIN" -avz --progress --update ${DRY_RUN_FLAG:+"$DRY_RUN_FLAG"} \
        "$REMOTE_SERVER:$REMOTE_MEDIA_PATH/" "$LOCAL_MEDIA_PATH/"; then
        print_error "Sync failed while downloading remote media"
        exit 1
    fi

    echo ""
    print_success "Two-way sync completed!"
}

show_status() {
    print_header "📊 Media Directory Status"

    check_ssh_connection

    print_info "Checking media directory sizes..."
    echo ""

    local remote_size
    local local_size
    local remote_count
    local local_count
    remote_size=$(get_remote_size)
    local_size=$(get_local_size)

    echo "Remote Server:"
    echo "  Path: $REMOTE_MEDIA_PATH"
    echo "  Size: $remote_size"
    echo ""
    echo "Local Machine:"
    echo "  Path: $LOCAL_MEDIA_PATH"
    echo "  Size: $local_size"
    echo ""

    # Show file counts
    if [ -d "$LOCAL_MEDIA_PATH" ]; then
        local_count=$(find "$LOCAL_MEDIA_PATH" -type f | wc -l | tr -d ' ')
        echo "Local files: $local_count"
    fi

    remote_count=$("$SSH_BIN" "$REMOTE_SERVER" "find '$REMOTE_MEDIA_PATH' -type f 2>/dev/null | wc -l" | tr -d ' ')
    echo "Remote files: $remote_count"
    echo ""
}

# Main script
if [ $# -eq 0 ]; then
    show_usage
    exit 0
fi

COMMAND="$1"
shift  # Remove command from arguments

case $COMMAND in
    download)
        download_media "$@"
        ;;
    upload)
        upload_media "$@"
        ;;
    sync)
        sync_media "$@"
        ;;
    status)
        show_status
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo ""
        show_usage
        exit 1
        ;;
esac
