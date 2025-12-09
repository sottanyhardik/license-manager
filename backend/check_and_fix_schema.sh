#!/bin/bash

# Database Schema Check and Fix Script
# This script checks and synchronizes database schema with Django models

set -e  # Exit on error

echo "================================================================================"
echo "Database Schema Check and Synchronization"
echo "================================================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo -e "${RED}Error: manage.py not found. Please run this script from the backend directory.${NC}"
    exit 1
fi

# Function to run management command
run_command() {
    python manage.py "$@"
}

echo "📊 Step 1: Checking current database structure..."
echo "--------------------------------------------------------------------------------"
run_command check_db_structure --show-columns

echo ""
echo "📋 Step 2: Checking for schema inconsistencies..."
echo "--------------------------------------------------------------------------------"
run_command sync_database_schema

echo ""
echo "🔍 Step 3: Checking for missing migrations..."
echo "--------------------------------------------------------------------------------"
run_command makemigrations --dry-run --verbosity 2

echo ""
echo -e "${YELLOW}Would you like to:${NC}"
echo "  1) Check only (already done above)"
echo "  2) Generate missing migrations"
echo "  3) Generate and apply migrations (full sync)"
echo "  4) Exit"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo -e "${GREEN}✅ Check complete. No changes made.${NC}"
        ;;
    2)
        echo ""
        echo "🔧 Generating migrations..."
        run_command makemigrations --verbosity 2
        echo -e "${GREEN}✅ Migrations generated. Run 'python manage.py migrate' to apply them.${NC}"
        ;;
    3)
        echo ""
        echo "⚠️  WARNING: This will modify your database!"
        echo "   Make sure you have a backup before proceeding."
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            echo ""
            echo "🔧 Step 1: Generating migrations..."
            run_command makemigrations --verbosity 2

            echo ""
            echo "🔧 Step 2: Showing migration SQL (review this carefully)..."
            # Get the last migration file for each app
            for app in core license bill_of_entry allotment trade accounts; do
                echo "--- SQL for app: $app ---"
                run_command sqlmigrate $app $(run_command showmigrations $app | grep '\[X\]' | tail -1 | awk '{print $2}' | cut -d_ -f1-2) 2>/dev/null || echo "No migrations found for $app"
            done

            echo ""
            read -p "Continue with applying migrations? (yes/no): " apply_confirm
            if [ "$apply_confirm" = "yes" ]; then
                echo ""
                echo "🔧 Step 3: Applying migrations..."
                run_command migrate --verbosity 2

                echo ""
                echo "🔧 Step 4: Final verification..."
                run_command sync_database_schema

                echo ""
                echo -e "${GREEN}✅ Database schema synchronized successfully!${NC}"
            else
                echo -e "${YELLOW}Cancelled. Migrations generated but not applied.${NC}"
            fi
        else
            echo -e "${YELLOW}Cancelled.${NC}"
        fi
        ;;
    4)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice.${NC}"
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo "Done!"
echo "================================================================================"
