---
paths:
  - "backend/**"
  - "master-data-service/**"
  - "mds-client/**"
---
# Backend rules (Django 6 / DRF / Python 3.14)

- Money/CIF/quantities: `Decimal` end-to-end (`to_decimal`, `DEC_0`, `quantize_2dp` from the existing helpers). No floats.
- Reuse services in `apps/*/services/` (e.g. `LicenseBalanceCalculator`) — never re-derive balance arithmetic in views/serializers.
- Bulk paths exist (`*_for_licenses`, `*_for_items`) — use them in lists/exports to avoid N+1.
- API contracts: do not rename/remove response fields or change status codes without an explicit request; add fields additively.
- Permissions: `apps/accounts/permissions.py` classes are part of the contract — never loosen them as a side effect.
- Migrations: one concern per migration; data migrations reversible where possible; `makemigrations --check --dry-run` must be clean (CI gate).
- Destructive data ops (deletes, unpairing, recovery) must be audited (see the existing `*RecoveryAudit` / unpair-and-delete audit patterns).
- Tests: `backend/tests/` (canonical suite) and `backend/apps/*/tests/` (run with `--import-mode=importlib`). Add tests for behaviour you change.
- Root-level `backend/verify_*.py`, `trace_*.py`, `test_*.py` are ad-hoc scripts, not part of the suite — do not run them against non-local DBs.
- Gates: `scripts/dev/quality-gate.sh backend` (and `mds` / `mds-client` for those services).
