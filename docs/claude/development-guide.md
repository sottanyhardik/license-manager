# Development Guide — Claude Context

> **How to make changes safely. Read before any implementation task.**

---

## Before You Start Any Task

1. Check `docs/README.md` for the relevant module doc
2. For balance/allotment/BOE changes: read `docs/claude/balance-context.md` first
3. Check `docs/improvements/improvement-register.md` — the task may already be documented
4. Run tests: `cd license-manager && .venv/bin/pytest backend/tests/ -q 2>&1 | tail -5`

---

## Project Structure Quick Reference

```
license-manager/
├── backend/            ← New Django app (feature/V1 development here)
│   ├── apps/           ← 9 Django apps
│   ├── config/         ← settings, urls, celery
│   ├── shared/         ← shared utilities
│   └── tests/          ← all tests
├── frontend/           ← New React app (feature/V1 development here)
│   └── src/
├── legacy/             ← READ-ONLY. Do not modify. Reference only.
├── docs/               ← THIS documentation
└── nginx-*.conf        ← Server configs
```

**Rule**: Never modify `legacy/`. It's the production read-only reference.

---

## Running the App Locally

```bash
# 1. Start Django backend (uses SQLite + managed=False patch)
SECRET_KEY="dev-local-key" nohup python /tmp/start-dev-server.py > /tmp/django-local.log &

# 2. Start Vite frontend
cd frontend && npm run dev &

# 3. Test via proxy
curl http://localhost:5173/api/v1/auth/login/ -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Admin credentials for local dev: admin / admin123
```

---

## Running Tests

```bash
# Full suite
.venv/bin/pytest backend/tests/ -q --tb=short

# Specific module
.venv/bin/pytest backend/tests/balance/ -v
.venv/bin/pytest backend/tests/integration/ -v

# With coverage
.venv/bin/pytest backend/tests/ --cov=apps --cov-report=term-missing
```

---

## Running Linters

```bash
# Backend lint (ruff)
.venv/bin/python -m ruff check backend/ --config backend/pyproject.toml

# Backend lint + auto-fix
.venv/bin/python -m ruff check backend/ --config backend/pyproject.toml --fix

# Frontend typecheck
cd frontend && node_modules/.bin/tsc --noEmit

# Frontend build (also typechecks)
cd frontend && npm run build
```

---

## Making a Backend Change

1. Read the relevant files (use `docs/` first, then source if needed)
2. Write the change in the appropriate service function (never in views/serializers)
3. Add/update tests
4. Run ruff: `.venv/bin/python -m ruff check backend/ --config backend/pyproject.toml --fix`
5. Run tests: `.venv/bin/pytest backend/tests/ -q`
6. Commit with descriptive message

**Template for service function docstring**:
```python
def my_function(param: type, ...) -> ReturnType:
    """
    One-line purpose.
    
    Business rule: what constraint this enforces.
    Side effects: what else changes (Celery task, plan update, etc.)
    Transaction: atomic/non-atomic.
    Raises: what exceptions and when.
    """
```

---

## Making a Frontend Change

1. Check `docs/frontend/architecture.md` for patterns
2. Make change in the appropriate feature directory
3. Ensure mutation `onSuccess` invalidates both list AND detail query keys
4. Run: `cd frontend && node_modules/.bin/tsc --noEmit && npm run build`
5. Commit

---

## Adding a New Business Rule

1. Implement in service layer (not views)
2. Add entry to `docs/business-rules/business-rule-index.md`
3. Write a test for it in the appropriate test file
4. If it's a calculation: add to `docs/business-rules/calculation-engine.md`

---

## Change Impact Assessment

Before modifying a critical file, ask: "What calls this?"

| File being changed | Check these files first |
|---|---|
| `balance_service.py` | `license/tasks.py`, `boe/models.py` (signals), `allotment_service.py` (_dispatch), `reports/services/balance_report.py` (divergence) |
| `allotment_service.py` | `allotment/views.py`, `tests/allotment/test_allotment.py` |
| `boe/models.py` | Everything that creates/deletes RowDetails (boe/views, boe_service, ledger upload) |
| `accounts/permissions.py` | All views that use permission classes; `tests/integration/test_permissions.py` |
| `accounts/serializers.py` | `UserSerializer` is used for login + /me — frontend auth depends on `is_superuser` field |
| `frontend/src/shared/api/client.ts` | All 9 feature modules import from it; auth interceptors critical |
| `frontend/src/shared/auth/AuthContext.tsx` | Every component that uses `useAuth()` |
| `frontend/src/app/globals.css` | All components using Tailwind color utilities |

---

## Commit Message Convention

```
type(scope): short description

Longer explanation if needed.
```

Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`, `style`  
Scope: module name (`balance`, `allotment`, `boe`, `trade`, `frontend`, `infra`, etc.)

Examples:
- `fix(balance): correct _dispatch to resolve license_id from item_id`
- `feat(allotment): add planning validation and LicenseItemPlan adjustment`
- `docs: add business rule index and calculation engine reference`
- `test(balance): 21 comprehensive business rule tests`

---

## Key File Locations Quick Reference

| What you need | File |
|---|---|
| Balance formula | `backend/apps/license/services/balance_service.py` |
| Allotment service | `backend/apps/allotment/services/allotment_service.py` |
| BOE signals | `backend/apps/bill_of_entry/models.py` (bottom of file) |
| Trade compute_amount | `backend/apps/trade/models.py:384-408` |
| Invoice number generator | `backend/apps/trade/models.py:66-112` |
| All RBAC roles | `backend/apps/accounts/permissions.py` + `frontend/src/shared/auth/roles.ts` |
| API client + interceptors | `frontend/src/shared/api/client.ts` |
| Sidebar RBAC gate | `frontend/src/shared/ui/Sidebar.tsx` (SidebarLink component) |
| Response envelope | `backend/shared/serializers.py` (EnvelopeMixin) |
| Pagination | `backend/shared/pagination.py` (StandardPagination) |
| Exception handler | `backend/shared/exceptions.py` (custom_exception_handler) |
| Django settings | `backend/config/settings/base.py` |
| Vite proxy | `frontend/vite.config.ts` |
| All API endpoints | `frontend/src/shared/api/endpoints.ts` |
| All routes | `frontend/src/shared/routes.ts` |
