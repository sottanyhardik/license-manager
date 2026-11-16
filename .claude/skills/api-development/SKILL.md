---
name: api-development
description: DRF API changes that preserve contracts and keep frontend clients in sync. Use when adding/changing endpoints, serializers, filters, pagination.
metadata:
  origin: project
---
Generic: ECC `api-design`. Specialist: `api-engineer`.

1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges. Find routes in `backend/apps/*/urls.py`, views/serializers via the index.
2. Contract: additive only — never rename/remove fields, change types, status codes, pagination or filter params, or error shape without an explicit request (flag `API CONTRACT CHANGE`).
3. Permissions classes from `apps/accounts/permissions.py`; every new endpoint has explicit permission + queryset scoping.
4. Avoid N+1: `select_related`/`prefetch_related`, bulk balance services.
5. Update the matching client/types in `frontend/src/api` in the same change.
6. Tests: API test for success + permission-denied + validation error. Review: `security-auditor` if auth/permissions touched.
