# Services

> Living document. One row per service function as implemented in `backend/`.
> Rule: Views call services. Services call the ORM. Services never call other views.

## Service Inventory

| Module | Service File | Function | Purpose | Status |
|---|---|---|---|---|
| license | apps/license/services/balance.py | recompute_license_balance(license_id) | Recalculate available_qty for all import items | pending |
| license | apps/license/services/license.py | create_license(...) | Create license + items in transaction.atomic | pending |
| trade | apps/trade/services/trade.py | create_trade(...) | Create trade + lines + payments atomically | pending |
| allotment | apps/allotment/services/allotment.py | create_allotment(...) | Create allotment + items atomically | pending |
| ... | | | | |

## Service Rules

1. All database writes inside `transaction.atomic()`
2. Services return domain objects, never HTTP responses
3. Services raise `ValidationError` or `PermissionDenied` — views catch and format
4. Balance recompute dispatched via Celery task (not called inline from signals)
5. No circular imports between services
