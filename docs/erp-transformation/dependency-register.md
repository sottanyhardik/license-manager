# Dependency register (OD-09)

Owner decision OD-09 (2026-11-15): adopt drf-spectacular and pip-audit. This register records every
dependency adopted under that decision. Add a row for each future adoption.

| Dependency | Version (exact pin) | Scope | Why | Where pinned |
|---|---|---|---|---|
| drf-spectacular | 0.30.0 | runtime (backend) | OpenAPI schema generation for DRF; documents existing contracts. Already pinned and wired before OD-09 (see below). Not changed. | `backend/requirements.txt` |
| pip-audit | 2.10.1 | CI / dev only (never runtime) | Python dependency vulnerability scanning. 2.10.1 is the latest release on PyPI and installs and runs on Python 3.14.10 (verified in a clean venv). | `backend/requirements-ci.txt` (not referenced by `requirements.txt` / `requirements-test.txt`) |

No second schema tool and no second package manager were introduced (pip only).

## drf-spectacular: state found (already wired, reused)

- Installed in the venv: 0.30.0 (Django 6.0.4, DRF 3.17.1).
- `INSTALLED_APPS` has `drf_spectacular`; `REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = drf_spectacular.openapi.AutoSchema`;
  `SPECTACULAR_SETTINGS` exists (`backend/lmanagement/settings.py`). Custom schema class in `backend/apps/core/openapi.py`.
- Routes in `backend/lmanagement/urls.py`: `/api/schema/`, `/api/docs/`, `/api/redoc/`.
  No settings or url changes were made by OD-09 work.

### Schema validation result

`manage.py spectacular --validate --fail-on-warn` **fails**: 22 warnings (6 unique), 0 errors.

| Category | Count (total / unique) | Detail |
|---|---|---|
| Path parameter type not derivable (`LicenseLedgerViewSetSchema` in `apps/core/openapi.py`) | 4 / 4 | `job_id`, `item_id`, `trade_id`, `request_id` default to "string"; fix with `@extend_schema(parameters=...)` |
| operationId collisions (resolved with numeral suffixes) | 2 / 2 | `license_ledger_download_package_readiness_retrieve`, `license_ledger_download_requests_retrieve` |
| Remaining warnings | 16 / 0 | repeats of the above across the generation passes |

(`Warnings: 22 (6 unique)` is the tool's own summary; the per-category split of the 16 repeats is inferred from the 6 unique messages.)

**CI runs without `--fail-on-warn` initially.** `scripts/dev/openapi_gate.sh` fails on any schema error and
ratchets warnings: the count may not exceed `OPENAPI_MAX_WARNINGS` (default 22). Lower it as warnings are fixed;
at 0 switch to `--fail-on-warn`. Warnings are not suppressed.

### Open owner decision: schema route permissions

Existing `urls.py`: `/api/schema|docs|redoc/` are **anonymous when `DEBUG=True`** and **any authenticated
user** when `DEBUG=False`. The OD-09 brief asked for staff/admin only. This was NOT changed because
`backend/tests/test_url_routing.py` (`test_schema_permission_class_wiring_matches_debug_flag`,
`test_schema_endpoint_accessible_when_authenticated_and_not_debug`) encodes the current contract ("IsAuthenticated, not
IsAdminUser"). Tightening it is a permission-contract change needing owner approval plus test updates.
(A trial change to a staff/superuser-only class was made and reverted; it failed those two tests as expected.)

## pip-audit

CI job `dependency-audit` (`.github/workflows/ci.yml`) and `scripts/dev/quality-gate.sh audit` run
`scripts/security/pip_audit_gate.py`, which runs pip-audit (full transitive resolution) over
`backend/requirements.txt` and `master-data-service/requirements-prod.txt`, prints every finding
(package, installed version, advisory id, fix versions), and exits non-zero for any advisory not covered by an
unexpired exception. Excepted findings are still printed. pip-audit failing to run is exit 2, never a pass.
pip-audit output carries no CVSS severity; look up severity on the GHSA/OSV page when triaging.

### Findings at adoption (2026-11-15, pip-audit 2.10.1)

Backend: 100 raw entries (duplicates across OSV/PyPI sources) = 75 unique advisories in 4 packages.
MDS (prod requirements): 30 raw = 18 unique, in 2 packages (Django, DRF, same advisories as backend).
Python-package vulnerabilities from the pip-audit run; **no runtime package was upgraded.**

| Package | Installed | Unique advisories | Scope | Fix version(s) | Example ids |
|---|---|---|---|---|---|
| Django | 6.0.4 | 13 | backend, mds | 6.0.5, 6.0.6, 6.0.7, 6.0.8 (6.0.8 clears all) | PYSEC-2026-50/54/55, 197-201, 2090-2092, 3717, 4035 |
| djangorestframework | 3.17.1 | 5 | backend, mds | 3.17.2 (2 advisories), 3.18.2 (3 advisories) | PYSEC-2026-3827/3828, CVE-2026-114136/7/8 |
| Pillow | 12.2.0 | 55 | backend | 12.3.0 (some), 13.0.0 (clears all) | PYSEC-2026-2253..2257, 3451..3454, 3493..3496, 4326..4363, ... |
| setuptools | 80.10.2 | 2 | backend | 83.0.0, 84.1.0 | PYSEC-2026-3447, GHSA-xmj3-9gf7-h52w |

The full per-advisory list (id, aliases, fix versions) is in `scripts/security/pip-audit-exceptions.json`.

### Recommended upgrades (need owner approval, not done)

1. Django 6.0.4 to 6.0.8 (patch release; also needed in `master-data-service/requirements.txt`).
2. djangorestframework 3.17.1 to 3.18.2 (minor; check DRF-3.18 / drf-spectacular 0.30.0 compatibility and run the API test suite).
3. Pillow 12.2.0 to 13.0.0 (major; check reportlab/docxtpl/pdf2image usage).
4. setuptools: runtime pin is `<81` because docxcompose still needs `pkg_resources`; both fixes (83.0.0, 84.1.0) are above that cap, so the setuptools findings cannot be cleared until docxcompose drops `pkg_resources` or the exposure is accepted. Setuptools is a build-time tool; the advisories concern building sdists / Windows wheels.

### Exceptions policy

- No finding is suppressed silently. An exception is a reviewed, dated entry in `scripts/security/pip-audit-exceptions.json`.
- Every entry needs `reason` and `expires` (YYYY-MM-DD, max 90 days out). Expired entries fail the gate.
- Entries are removed when the package is upgraded (the gate does not fail on stale entries; clean them up on upgrade).
- Adding or renewing an entry requires owner approval in the PR.
- Format:

```json
{
  "schema": 1,
  "exceptions": [
    {
      "id": "PYSEC-2026-50",
      "aliases": ["GHSA-7h2m-m8vj-598h", "CVE-2026-35192"],
      "package": "django",
      "version": "6.0.4",
      "fix_versions": ["6.0.5"],
      "scopes": ["backend", "mds"],
      "reason": "pre-existing — pending owner upgrade decision",
      "expires": "2027-01-15"
    }
  ]
}
```

Matching is by package name plus any of `id` / `aliases`; `scopes` is `backend` and/or `mds`.

**All 75 current entries are "pre-existing — pending owner upgrade decision", expiring 2027-01-15.** The gate is
green only because of these exceptions; it turns red on that date unless the upgrades land or the owner renews.
