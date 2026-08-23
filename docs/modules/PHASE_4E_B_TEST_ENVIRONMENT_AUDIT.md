# Phase 4E-B Test Environment Audit
**Date:** 2026-08-10  
**Status:** Environment Available  
**Task:** Recover test environment and execute Phase 4E-B verification suite

---

## ENVIRONMENT DISCOVERY

### Python & Virtual Environment
```
VirtualEnv: .venv (present and active)
Python: 3.14.6
Pip: Available
```

### Installed Test Dependencies
```
pytest: 8.3.4 ✅
pytest-django: (checking...)
pytest-cov: (checking...)
Django: 6.0.4 ✅
```

### CI/CD Configuration
**File:** `.github/workflows/ci.yml`  
**Backend Test Job:** Lines 45-115

**Exact CI command:**
```bash
pytest tests/ -p no:cacheprovider
```

**Optional (advisory):**
```bash
pytest apps/license/tests apps/core/tests --import-mode=importlib -p no:cacheprovider
```

### CI Environment Variables
```
DJANGO_SETTINGS_MODULE: lmanagement.settings
TESTING: true
SECRET_KEY: ci-not-a-secret-key-for-tests-only
DB_NAME: lmanagement
DB_USER: lmanagement
DB_PASS: lmanagement
DB_HOST: localhost
DB_PORT: 5432
REDIS_URL: redis://localhost:6379/0
```

### CI Services
1. **PostgreSQL 16**
   - Port: 5432
   - Database: lmanagement
   - User: lmanagement
   - Pass: lmanagement

2. **Redis 7**
   - Port: 6379

### Test Requirements
**File:** `backend/requirements-test.txt`

```
pytest==8.3.4
pytest-django==4.9.0
pytest-cov==6.0.0
pytest-xdist==3.6.1
requests==2.32.3
faker==33.1.0
flake8==7.1.1
coverage[toml]==7.6.10
```

---

## LOCAL ENVIRONMENT STATUS

### Available
✅ Python 3.14.6  
✅ .venv configured  
✅ pytest 8.3.4 installed  
✅ Django 6.0.4 installed  
✅ requirements-test.txt present  

### Required But Not Local
❌ PostgreSQL 16 (running service)  
❌ Redis 7 (running service)  
❌ Environment variables (need to set)

---

## DATABASE REQUIREMENT

### Current: Production Configuration
Django is likely configured to use PostgreSQL by default.

### For Local Testing: Two Approaches

**Option A: Docker Compose (Preferred)**
- Mirrors CI exactly
- Services: PostgreSQL + Redis
- Isolation: Clean test database each run

**Option B: SQLite (Alternative)**
- Check if Django test settings support in-memory SQLite
- Faster but may not capture all production semantics
- Only if PostgreSQL service unavailable

### Decision Required
The financial parity verification for Ledger MUST use the same database engine semantics as production (PostgreSQL).

If using SQLite, transaction ordering, isolation, and concurrent access semantics may differ.

---

## NEXT STEPS FOR ENVIRONMENT RECOVERY

### Step 1: Verify pytest-django Configuration
```bash
cd backend
.venv/bin/pytest --collect-only tests/ 2>&1 | head -50
```

Expected output shows test discovery without errors.

### Step 2: Check Django Settings
```python
# Expected in lmanagement/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'lmanagement',
        # ...
    }
}

# For testing, should use:
if os.getenv('TESTING'):
    # Use test database
```

### Step 3: Set Up Services
**Option: Docker Compose (if available)**
```bash
docker-compose up -d postgres redis
```

**Option: Local PostgreSQL/Redis Installation**
(Check if services available on localhost)

### Step 4: Create Test Database
```bash
cd backend
export DJANGO_SETTINGS_MODULE=lmanagement.settings
export TESTING=true
export DB_HOST=localhost
export DB_NAME=lmanagement
export DB_USER=lmanagement
export DB_PASS=lmanagement
export REDIS_URL=redis://localhost:6379/0

.venv/bin/python manage.py migrate
```

### Step 5: Run Canonical Tests
```bash
.venv/bin/pytest apps/license/tests/test_canonical_ledger_service.py -v
```

### Step 6: Run PDF Tests
```bash
.venv/bin/pytest apps/license/tests/test_ledger_pdf_live_balance.py -v
```

### Step 7: Run All Ledger Tests
```bash
.venv/bin/pytest apps/license/tests -k "ledger or canonical or pdf" -v
```

---

## CRITICAL DECISION

**Can we run tests locally?**

This depends on:
1. Whether PostgreSQL/Redis can be accessed or started
2. Whether Docker is available for spin-up

If neither is available:

```
GATE 4E-B = BLOCKED

Environment:
BLOCKED (no PostgreSQL/Redis service)

Next Action:
Configure Docker or install local services
```

If both are available:

```
Proceed to test execution
```

---

## TEST FILE LOCATIONS

Based on CI configuration, tests are in:

1. `tests/` (canonical suite)
2. `apps/license/tests/` (advisory - balance/duty/core math)
3. `apps/core/tests/` (advisory - utilities)

**Phase 4E-B relevant tests:**
- `apps/license/tests/test_canonical_ledger_service.py`
- `apps/license/tests/test_ledger_pdf_live_balance.py`
- `apps/license/tests/test_ledger_api_canonical_migration.py` (if exists)

---

## REPORT STATUS

**Environment Type:** Local + Services Required  
**Python:** Ready  
**pytest:** Ready  
**Django:** Ready  
**PostgreSQL:** Required  
**Redis:** Required  
**Status:** Can proceed IF services available

---

**Next Action:** Determine if PostgreSQL/Redis can be started, then proceed to Step 5 above.

