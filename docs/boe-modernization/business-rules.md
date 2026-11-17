# BOE business rules

This file summarises BOE behaviour and links to the authoritative sources. It does not copy them.

- Approved decisions (source of truth): [owner-decisions.md](owner-decisions.md)
- Canonical CIF/balance rule and code map: `../../.claude/rules/business-rules.md`
- Frozen by owner (no change allowed): canonical CIF rule, the `LicenseBalanceCalculator` engines, A-2 (`calculate_balance.py` hidden-BOE handling of stored quantity), Total Allotted. Balance refresh triggers may be added; balance math may not change.
- Escalation history (superseded): `../erp-architecture/boe-modernization-progress.md` (escalations 1-15)

## Decision map

| Decision | Rule (short) | Where implemented | Status |
|---|---|---|---|
| D1 | Changing invoice_no on a genuinely hidden BOE returns 400 (update-invoice-no, PUT, PATCH). Legacy free-text OTH on never-hidden BOEs stays editable. | `boe_service.py` `invoice_no_change_blocked`; serializer shim | Phase A |
| D2 | BOE_VIEWER is read-only except POST update-invoice-no | `accounts/permissions.py` | Phase A |
| D3 | Form updates never delete `is_frozen=True` rows | `boe_service.py` `_upsert_rows`, `_delete_orphan_rows` | Phase A (and refactored B3) |
| D4 | Merge: frozen BOE priority; lock both, persist exchange rate, reject when exactly one is genuinely hidden, atomic, refresh on commit | `boe_service.py` `merge_boe` (l.579) | Phase A |
| D5 | Moving RowDetails refreshes old and new licence/item | balance refresh path | Phase A |
| D6 | Restore uses genuine-hidden audit, never `invoice_no=='OTH'` | `boe_service.py` restore path | Phase A |
| D7 | Missing date on create/update returns structured 400 with existing id where safe; DB uniqueness kept | `save_boe_with_rows` / `_create_boe` | Phase A (moved in B3) |
| D8 | fetch-allotment-details: invalid id 400, unknown 404 | allotment lookup view | Phase A |
| D9 | parse-pdf `create_company` default false; creation needs company-write permission and MDS gate; no raw exception text | `api/views_parse_pdf.py` l.253, l.298 | Phase A |
| D10 | PDF copy name `BOE_<NO>_<DATE>.pdf`; PDF signature check; inline only for real PDFs, else attachment and octet-stream | `core/views/media.py` `_boe_download_meta` (l.108-115) | Phase A |
| D11 | Overview default tab; shared ActionMenu; ConfirmProvider; role gating | BoeDetailPage, `useBoeRowActions` | Phase A + B1 |
| D12 | M2M link/unlink and INDIVIDUAL_ITEM ceiling characterised, then fixed | `boe_service.py` `check_individual_item_cif_ceiling` (l.102) | Phase A |
| D13 | Unchanged row not failed by own debit counted twice | `check_individual_item_cif_ceiling` docstring | Phase A |
| D14 | planning_target_item preserved on PATCH with validation | `save_boe_with_rows` / `_update_boe` | Phase A |
| D15 | Numeric-string ids accepted for bulk hide/restore | bulk hide/restore views | Phase A |

## Known limitations (documented, not fixed)

- INDIVIDUAL_ITEM ceiling ignores payload allotments (documented limitation, Phase A).

## Enforced merge guard

- Merge rejects removing a BOE that has trade or invoice links (`boe_service.py` l.499-518, l.663-671, with the ProtectedError path returning 400).
