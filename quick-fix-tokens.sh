#!/bin/bash
# Quick fix for JWT token blacklist foreign key error

echo "🔧 Fixing JWT Token Blacklist..."
echo ""

# Clear token blacklist tables
echo "Clearing token blacklist tables..."
psql -U lmanagement -d lmanagement << EOF
TRUNCATE TABLE token_blacklist_outstandingtoken CASCADE;
TRUNCATE TABLE token_blacklist_blacklistedtoken CASCADE;
EOF

if [ $? -eq 0 ]; then
    echo "✅ Token tables cleared successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Restart your Django server"
    echo "2. Clear browser localStorage (or use incognito mode)"
    echo "3. Log in again"
else
    echo "❌ Failed to clear tables. Trying alternative method..."
    echo ""

    # Alternative: Drop and recreate constraint
    psql -U lmanagement -d lmanagement << EOF
    -- Drop old constraint
    ALTER TABLE token_blacklist_outstandingtoken
    DROP CONSTRAINT IF EXISTS token_blacklist_outs_user_id_83bc629a_fk_auth_user;

    -- Add new constraint
    ALTER TABLE token_blacklist_outstandingtoken
    ADD CONSTRAINT token_blacklist_outs_user_id_83bc629a_fk_accounts_user
    FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE;

    -- Clear old data
    DELETE FROM token_blacklist_outstandingtoken WHERE user_id NOT IN (SELECT id FROM accounts_user);
EOF

    if [ $? -eq 0 ]; then
        echo "✅ Foreign key constraint updated!"
    else
        echo "❌ Manual intervention needed. See FIX_TOKEN_BLACKLIST.md"
    fi
fi
