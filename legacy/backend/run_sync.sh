#!/bin/bash
# Run license sync command to update all flags with correct business rules

echo "======================================"
echo "Starting License Sync"
echo "======================================"
echo ""
echo "This will update:"
echo "  - balance_cif (calculated from exports/imports/allotments/BOE)"
echo "  - is_null (balance < \$500)"
echo "  - is_expired (expiry < today)"
echo "  - import item balances"
echo ""
echo "Processing 2075 licenses..."
echo ""

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Run the sync command
python manage.py sync_licenses

echo ""
echo "======================================"
echo "Sync Complete!"
echo "======================================"
echo ""
echo "Refresh your dashboard to see accurate counts."
