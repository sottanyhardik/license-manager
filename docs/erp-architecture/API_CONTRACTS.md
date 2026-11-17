# API contracts (hub)

Frozen standards: [api-contract-standards.md](api-contract-standards.md) (pagination, envelopes, error shapes,
permissions). Endpoint catalogue: `docs/04-api.md`. Contract tests: `backend/apps/bill_of_entry/tests/test_boe_api_contract.py`
(pattern to copy for other modules). Frontend clients: `frontend/src/api/`.

Rules: no response-shape change without an explicit **API CONTRACT CHANGE** flag and owner approval;
TypeScript interfaces in `frontend/src/api` are updated in the same commit as the serializer.

Latest addition: grouped licence overview transactions endpoint (`9a4dcf94`,
`backend/apps/license/api/views/license_overview_transactions.py`).

**API CONTRACT CHANGE (additive, 2026-11-17, `331b9520`):** `GET/PATCH/DELETE /api/masters/notification-numbers/<code>/`
now resolves codes containing `/` (e.g. `025/2023`); previously 404. Response shapes unchanged. Generic metadata for
`unit-prices` now lists `unit_price` in `form_fields`.
