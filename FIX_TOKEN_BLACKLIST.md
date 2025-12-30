# Fix Token Blacklist Foreign Key Error

## Problem
```
django.db.utils.IntegrityError: insert or update on table "token_blacklist_outstandingtoken"
violates foreign key constraint "token_blacklist_outs_user_id_83bc629a_fk_auth_user"
DETAIL: Key (user_id)=(4) is not present in table "auth_user".
```

This happens because:
1. The JWT token blacklist tables reference the old default `auth_user` table
2. Your custom User model is in `accounts_user` table
3. The migration from old role system may have changed user IDs

## Solution Options

### Option 1: Clear Token Blacklist Tables (Recommended for Development)

This will log out all users but fixes the issue immediately:

```bash
cd backend

# Connect to PostgreSQL
psql -U lmanagement -d lmanagement

# Clear the token blacklist tables
TRUNCATE TABLE token_blacklist_outstandingtoken CASCADE;
TRUNCATE TABLE token_blacklist_blacklistedtoken CASCADE;

# Exit psql
\q
```

Then restart your Django server.

### Option 2: Migrate Token Blacklist to Use Custom User Model

1. **Check current migrations:**
```bash
cd backend
python manage.py showmigrations token_blacklist
```

2. **Run migrations again:**
```bash
python manage.py migrate token_blacklist
```

3. **If migration fails, fake it and clear data:**
```bash
# Fake the migration
python manage.py migrate token_blacklist --fake

# Then use Option 1 to clear the tables
```

### Option 3: Update Foreign Key Constraint (Advanced)

```sql
-- Connect to database
psql -U lmanagement -d lmanagement

-- Drop the old constraint
ALTER TABLE token_blacklist_outstandingtoken
DROP CONSTRAINT IF EXISTS token_blacklist_outs_user_id_83bc629a_fk_auth_user;

-- Add new constraint pointing to accounts_user
ALTER TABLE token_blacklist_outstandingtoken
ADD CONSTRAINT token_blacklist_outs_user_id_83bc629a_fk_accounts_user
FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE;

-- Do the same for blacklistedtoken if it has a user_id
-- (Note: blacklistedtoken usually references outstandingtoken, not user directly)

\q
```

## Recommended Steps

**For Development Environment:**

1. Clear the token tables (Option 1)
2. All users will need to log in again
3. Continue development

```bash
# Quick fix:
cd backend
psql -U lmanagement -d lmanagement -c "TRUNCATE TABLE token_blacklist_outstandingtoken CASCADE;"
```

**For Production Environment:**

1. Backup database first
2. Use Option 3 to update the foreign key constraint
3. This preserves existing tokens

## After Fix

1. Restart Django server
2. Clear browser cache/localStorage
3. Log in again
4. Verify login works without errors

## Prevention

After applying the fix, run all migrations:

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

This ensures all tables are properly aligned with your custom User model.

## Verify Fix

After applying the solution, test login:

```bash
# Check if tables are empty
psql -U lmanagement -d lmanagement -c "SELECT COUNT(*) FROM token_blacklist_outstandingtoken;"

# Try logging in via curl
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'
```

If login succeeds, the fix worked!
