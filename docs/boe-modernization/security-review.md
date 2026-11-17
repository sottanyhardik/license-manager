# Security review (BOE)

## Permissions

| Control | Location | Evidence |
|---|---|---|
| BOE_VIEWER read-only, one exception (POST update-invoice-no) | `backend/apps/accounts/permissions.py` l.63-70, 92, 164-169, 189, 233, 296 | D2; positive and negative tests in Phase A |
| Route guard on `/bill-of-entries/:id` | `frontend/src/routes/AppRoutes.tsx` (BOE_LIST_ROLES) | Route guard has NO test (renders not through ProtectedRoute). Open. |
| Edit gated on BOE_MANAGER, Transfer Letter on BOE_TRANSFER_LETTER_ROLES | BoeDetailPage, `useBoeRowActions` | B1 tests (manager/viewer/TL) |
| Viewer test | BoeDetailPage.test.tsx | Only checks no actions menu appears |

## PDF handling

| Item | State | Location |
|---|---|---|
| parse-pdf create_company default false (D9) | Implemented | `backend/apps/bill_of_entry/api/views_parse_pdf.py` l.253, l.298 |
| Company creation needs company-write permission and MDS gate (D9) | Per Phase A decision; verify on review | views_parse_pdf.py `_match_or_create_company` (l.93) |
| No raw exception text to clients (D9) | Per Phase A | views_parse_pdf.py |
| PDF copy download: inline only for real `%PDF-`, else attachment + octet-stream (D10) | Implemented | `backend/apps/core/views/media.py` l.108-115, 181-199 |
| Copy filename `BOE_<NO>_<DATE>.pdf`, sanitised | Per D10 | media.py `_boe_download_meta` |

## Media serving and nosniff

- `nginx-protected-media.conf` (repo root) sets `add_header X-Content-Type-Options "nosniff" always;` in the internal `/protected-media/` block (l.23-27). The other nginx site configs already carry nosniff.
- NOT DEPLOYED. Ops steps and verification are in `nginx-nosniff-deployment.md`.
- Note from the file: add_header in a location replaces server-level headers, so any server-level headers needed on media must be repeated in that block.

## Escalated security items

| Item | Owner decision | Status |
|---|---|---|
| parse-pdf create_company default | D9 approved | Implemented (Phase A) |
| boe_pdf_copy inline serving and validation | D10 approved | Implemented in `media.py`; nginx nosniff pending deployment |
| Insider stored XSS via PDF copy | D10 | Mitigated in app code; full mitigation needs nosniff deployed |

## Open items

1. Route guard test for BOE_LIST_ROLES on the detail route (no test today).
2. nginx nosniff not deployed (ops).
3. Viewer read-only test on detail page is weak (only checks the menu is absent).
