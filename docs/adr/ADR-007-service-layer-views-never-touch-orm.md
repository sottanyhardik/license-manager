# ADR-007 — Service Layer: Views Never Touch ORM

**Status:** Accepted
**Date:** 2026-07-14

## Context

The legacy codebase suffers from a fat-views pattern: Django views directly
call ORM queries, apply business logic (balance calculations, validation rules,
conditional state transitions), and return serialized responses. This makes
individual pieces of logic hard to test in isolation, hard to reuse across
views (e.g. the same balance recompute is copy-pasted across three views), and
hard to reason about when debugging production issues.

A clean architectural boundary between HTTP handling and business logic is
required in the new app.

## Decision

All database reads and writes in the new app go through **plain Python service
functions** in `apps/<module>/services/`.

The rule: **Views never touch the ORM directly.**

Structural contracts:

1. **Views** (DRF `APIView` or `ViewSet`) do exactly three things: authenticate
   the request, call a service function, and return an HTTP response.
2. **Serializers** validate and deserialize input. They do not contain business
   logic and do not call the ORM or services.
3. **Service functions** contain all business logic: ORM queries, calculations,
   state transitions, and cross-model coordination. They are plain Python
   functions (not classes) unless a class genuinely reduces complexity.
4. **Models** contain field definitions, `__str__`, `Meta`, and simple property
   methods that derive values from the instance's own fields only. No ORM
   calls from model methods (no `self.related_set.filter(...)`).
5. **Signals** are used only for within-app audit logging (see ADR-008). No
   cross-app side-effect logic in signals.
6. **All writes in service functions are wrapped in `transaction.atomic()`.**
   Partial writes that leave the DB in an inconsistent state are not acceptable.

Example layout:

```
apps/licenses/
    views.py          # LicenseViewSet — calls services, returns Response
    serializers.py    # LicenseSerializer — validation only
    services/
        license_service.py    # create_license(), update_license(), close_license()
        balance_service.py    # recompute_balance(), get_balance_summary()
    models.py         # License, LicenseItem — fields + Meta only
```

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Fat models (business logic on model methods) | Model methods cannot be easily mocked; business logic that spans multiple models ends up on one model arbitrarily; encourages hidden ORM calls inside property accessors. |
| Fat views (business logic in views/viewsets) | Logic is not reusable across views; view tests become integration tests; HTTP-layer concerns (status codes, headers) mix with business concerns (balance validity, state machine transitions). |
| Repository pattern (Repository class per model) | Useful at microservice scale with multiple data stores; for this application's scale, a plain-function service layer provides the same testability benefit with less boilerplate. |
| Django class-based services (service classes) | Stateless service functions are simpler to import, test, and mock than instantiated service objects. Classes are used only when there is genuine state to maintain across calls (rare). |

## Consequences

**Positive:**
- Service functions can be unit-tested with `pytest` and `factory-boy` without
  an HTTP request: `assert create_license(data) returns a License instance`.
- The same service function is called identically from a REST view, a
  management command, a Celery task, and a test — no duplication.
- `transaction.atomic()` on every write means the DB is never left in a
  half-written state if an exception is raised mid-function.
- Code review is simpler: a PR touching `views.py` should contain no ORM
  calls; reviewers can enforce this mechanically.

**Negative:**
- Developers must resist the temptation to add ORM calls to serializers
  (`validate_*` methods) or model methods. Code review discipline is required.
- The service layer adds one extra call stack frame per request; this is
  negligible at the application's scale.
- Large service files must be split proactively (e.g. `balance_service.py`
  separate from `license_service.py`) or they reproduce the fat-views problem
  at a different layer.

## Related ADRs

- ADR-003 — Backend Tech Stack
- ADR-008 — Signal Strategy: Celery Replaces Cross-App Signals
