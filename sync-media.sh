#!/bin/bash

# Media Sync Script
# Syncs media files from production server to local machine
# Deletes old local media files before syncing

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVER="django@143.110.252.201"
REMOTE_MEDIA_PATH="/home/django/license-manager/backend/media"
LOCAL_MEDIA_PATH="/Users/hardiksottany/PycharmProjects/license-manager/backend/media"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}🔄 Media Sync Script${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Step 1: Check if local media directory exists
if [ -d "$LOCAL_MEDIA_PATH" ]; then
    echo -e "${YELLOW}→ Local media directory exists${NC}"

    # Get size of local media
    LOCAL_SIZE=$(du -sh "$LOCAL_MEDIA_PATH" 2>/dev/null | cut -f1)
    echo -e "${BLUE}→ Current local media size: ${LOCAL_SIZE}${NC}"

    # Ask for confirmation before deleting
    echo -e "${RED}→ This will DELETE all existing local media files${NC}"
    read -p "Continue? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}✗ Sync cancelled${NC}"
        exit 1
    fi

    # Delete old local media
    echo -e "${YELLOW}→ Deleting old local media files...${NC}"
    rm -rf "$LOCAL_MEDIA_PATH"/*
    echo -e "${GREEN}✓ Old media files deleted${NC}"
else
    echo -e "${YELLOW}→ Creating local media directory...${NC}"
    mkdir -p "$LOCAL_MEDIA_PATH"
    echo -e "${GREEN}✓ Local media directory created${NC}"
fi

echo ""
echo -e "${BLUE}→ Getting remote media size...${NC}"
REMOTE_SIZE=$(ssh $SERVER "du -sh $REMOTE_MEDIA_PATH 2>/dev/null | cut -f1")
echo -e "${BLUE}→ Remote media size: ${REMOTE_SIZE}${NC}"
echo ""

# Step 2: Sync media from server using rsync
echo -e "${BLUE}→ Syncing media from server...${NC}"
echo -e "${BLUE}→ Source: ${SERVER}:${REMOTE_MEDIA_PATH}/${NC}"
echo -e "${BLUE}→ Destination: ${LOCAL_MEDIA_PATH}/${NC}"
echo ""

# Use rsync for efficient transfer
# -a: archive mode (preserves permissions, timestamps, etc.)
# -v: verbose
# -z: compress during transfer
# -h: human-readable progress
# --progress: show progress
# --delete: delete files in destination that don't exist in source
rsync -avzh --progress \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.DS_Store' \
    "${SERVER}:${REMOTE_MEDIA_PATH}/" \
    "${LOCAL_MEDIA_PATH}/"

echo ""
echo -e "${GREEN}✓ Media sync completed${NC}"

# Step 3: Show summary
LOCAL_SIZE_AFTER=$(du -sh "$LOCAL_MEDIA_PATH" 2>/dev/null | cut -f1)
FILE_COUNT=$(find "$LOCAL_MEDIA_PATH" -type f | wc -l | tr -d ' ')

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}📊 Sync Summary${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✓ Remote media size: ${REMOTE_SIZE}${NC}"
echo -e "${GREEN}✓ Local media size: ${LOCAL_SIZE_AFTER}${NC}"
echo -e "${GREEN}✓ Total files synced: ${FILE_COUNT}${NC}"
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}🎉 Media sync completed successfully!${NC}"
echo -e "${GREEN}================================================${NC}"
