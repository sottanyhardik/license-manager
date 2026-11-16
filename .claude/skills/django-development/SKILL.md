---
name: django-development
description: License Manager Django 6/DRF/Celery conventions. Use when writing or changing backend code.
metadata:
  origin: project
---
Rules: `.claude/rules/backend.md` (auto-loaded for `backend/**`). Generic patterns: ECC skills `django-patterns`, `django-celery`, `django-security`.

1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges.
2. Reuse services in `apps/*/services/` — never re-derive balance math in views/serializers; use bulk `*_for_licenses` / `*_for_items` paths in lists.
3. `Decimal` end-to-end for money/CIF/qty (existing `to_decimal`, `DEC_0`, `quantize_2dp`).
4. Permissions in `apps/accounts/permissions.py` are contract — never loosen.
5. Tests: `backend/tests/` + `backend/apps/*/tests/` (`--import-mode=importlib` for app tests). Targeted run: `cd backend && python -m pytest <path>::<test> -p no:cacheprovider`.
6. Gate: `sh scripts/dev/quality-gate.sh backend`. Migrations → skill `migration-safety`.
