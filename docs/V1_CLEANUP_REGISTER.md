# V1 Cleanup Register

Companion to [V1_MASTER_TRACKER.md](./V1_MASTER_TRACKER.md). Governed by DEC-004 and DEC-005.

Classes: Active · Required · Historical · Duplicate · Obsolete · Unused · Unknown.

No item may be moved or removed until its reference check is recorded. Reference checks cover imports, scripts, CI, deployment, developer docs and runtime use. Never remove migrations, production configuration, operational scripts or user data.

| Item | Class | Evidence | Action | Status |
|---|---|---|---|---|
| `backend/apps/accounting/` | Unknown | Empty directory. Not in `INSTALLED_APPS`. No git-tracked files. | Confirm no imports, then remove. | OPEN |
| `docs/v1/business-requirements/*.md` (2 files) | Unknown | Untracked. Provenance not known. | Read first. Keep until classified. | OPEN |
| Root sample and scratch folders (`SAMPLE/`, `adf/`, `backups/`, `exc_pdf/`, `logs/`, `tmp/`) | Unknown | Present on disk. Classification not done. | Check references and `.gitignore`. | OPEN |
| `master-data-service/`, `mds-client/` | Unknown | Settings import `mds_client` conditionally. `master-data-service/` has not been checked. | Keep both until references are checked. | OPEN |
| `free-react-tailwind-admin-dashboard-main/` | Unknown | Third-party template folder. | Check whether any code imports it. | OPEN |
| One-off root and `backend/` debug scripts (`parity_*.py`, `reconciliation_*.py`, `verify_*.py`, `deep_trace.py`, `final_debug.py`, `trace_*.py`, `test_*.py` at backend root) | Unknown | Not run by pytest, which collects `tests` and `apps` only. | Check CI and docs references, then classify. | OPEN |
| `frontend/route-browser-test.js` | Duplicate, Unused | Removed in this pass. Reference search found no references. `route-browser-test.mjs` is a near-twin (11-line diff). It used `require` in an ESM package and failed lint. Recover with `git show HEAD:frontend/route-browser-test.js`. | Removed. ISS-017. | DONE |
| `.env` (tracked by git, 0 bytes at inventory) | Required, but a security risk if it holds secrets | ISS-013 | Confirm contents and history. Untrack only with approval. | OPEN |
| `docs/` legacy material (~200 files across `architecture/`, `audit/`, `modules/`, `guides/`, `operations/`) | Historical / to audit | DEC-005 | Audit, migrate, then archive. Do not delete. | OPEN |
