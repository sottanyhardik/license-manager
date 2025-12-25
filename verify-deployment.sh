#!/bin/bash

# Deployment Verification Script
# Checks all prerequisites before running auto-deploy.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVERS=("143.110.252.201" "139.59.92.226")
SERVER_USER="django"
PASSWORD="admin"
BRANCH="version-4.1"

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}→ $1${NC}"
}

ERRORS=0
WARNINGS=0

print_header "🔍 Pre-Deployment Verification"

# Check 1: Local git status
print_info "Checking local git status..."
if git diff-index --quiet HEAD --; then
    print_success "No uncommitted changes"
else
    print_warning "You have uncommitted changes"
    WARNINGS=$((WARNINGS + 1))
fi

# Check 2: Current branch
print_info "Checking current branch..."
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" == "$BRANCH" ]; then
    print_success "On correct branch: $BRANCH"
else
    print_error "Wrong branch: $CURRENT_BRANCH (expected: $BRANCH)"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: Remote is up to date
print_info "Checking if remote is up to date..."
git fetch origin $BRANCH --quiet 2>/dev/null || true
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "")

if [ -z "$REMOTE" ]; then
    print_warning "Could not check remote status (no upstream configured)"
    WARNINGS=$((WARNINGS + 1))
elif [ "$LOCAL" = "$REMOTE" ]; then
    print_success "Local and remote are in sync"
elif [ "$LOCAL" != "$REMOTE" ]; then
    AHEAD=$(git rev-list --count origin/$BRANCH..$BRANCH 2>/dev/null || echo "0")
    BEHIND=$(git rev-list --count $BRANCH..origin/$BRANCH 2>/dev/null || echo "0")

    if [ "$AHEAD" -gt 0 ]; then
        print_warning "You have $AHEAD unpushed commit(s)"
        WARNINGS=$((WARNINGS + 1))
    fi
    if [ "$BEHIND" -gt 0 ]; then
        print_warning "You are $BEHIND commit(s) behind remote"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# Check 4: Frontend package.json exists
print_info "Checking frontend configuration..."
if [ -f "frontend/package.json" ]; then
    print_success "Frontend package.json exists"
else
    print_error "Frontend package.json not found"
    ERRORS=$((ERRORS + 1))
fi

# Check 5: Backend requirements.txt exists
print_info "Checking backend configuration..."
if [ -f "backend/requirements.txt" ]; then
    print_success "Backend requirements.txt exists"
else
    print_error "Backend requirements.txt not found"
    ERRORS=$((ERRORS + 1))
fi

# Check 6: SSH connectivity
print_header "🔌 Testing Server Connectivity"

for SERVER in "${SERVERS[@]}"; do
    print_info "Testing connection to $SERVER..."

    if command -v sshpass &> /dev/null; then
        if sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$SERVER_USER@$SERVER" "echo 'Connected'" 2>/dev/null | grep -q "Connected"; then
            print_success "SSH connection to $SERVER: OK"
        else
            print_error "SSH connection to $SERVER: FAILED"
            ERRORS=$((ERRORS + 1))
        fi
    else
        print_warning "sshpass not installed, trying regular SSH..."
        if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SERVER_USER@$SERVER" "echo 'Connected'" 2>/dev/null | grep -q "Connected"; then
            print_success "SSH connection to $SERVER: OK (key-based)"
        else
            print_error "SSH connection to $SERVER: FAILED"
            print_info "  Install sshpass or setup SSH keys"
            ERRORS=$((ERRORS + 1))
        fi
    fi
    echo ""
done

# Summary
print_header "📊 Verification Summary"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    print_success "All checks passed! Ready to deploy."
    echo ""
    print_info "To deploy, run:"
    echo "    ./auto-deploy.sh"
    echo ""
    exit 0
elif [ $ERRORS -eq 0 ]; then
    print_warning "$WARNINGS warning(s) found"
    print_info "You can proceed with deployment, but review warnings above"
    echo ""
    print_info "To deploy, run:"
    echo "    ./auto-deploy.sh"
    echo ""
    exit 0
else
    print_error "$ERRORS error(s) and $WARNINGS warning(s) found"
    print_error "Please fix errors before deploying"
    echo ""
    exit 1
fi
