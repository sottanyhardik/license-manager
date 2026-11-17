# Financial integrity review (BOE)

Scope: the BOE write path, merge, frozen rows, CIF ceiling and balance refresh. No balance math was changed (A-2, engines, Total Allotted frozen).

## Controls

| Area | Control | Location | Status |
|---|---|---|---|
| Frozen rows | Form updates never delete or overwrite `is_frozen=True` rows, even if omitted (D3) | `services/boe_service.py` `_upsert_rows` (l.1416), `_delete_orphan_rows` (l.1463) | Implemented; characterised in B3 |
| Hidden BOE invoice number | 400 on genuinely hidden BOE (D1) | `invoice_no_change_blocked`; serializer shim | Implemented |
| Restore collision | Uses genuine-hidden audit, never invoice_no=='OTH' (D6) | restore path in boe_service.py | Implemented |
| Merge | Frozen priority; lock both; persist exchange rate; reject if exactly one genuinely hidden; reject removing BOEs with trade/invoice links; atomic (D4) | `merge_boe` (l.579), guard l.499-518, l.663-671 | Implemented |
| Old/new refresh on row move | Refresh old and new licence/item, no duplicate refresh (D5) | balance refresh path | Implemented (CIF auditor review required) |
| INDIVIDUAL_ITEM ceiling | new_total <= credit - debit + own_counted; unchanged writes never fail (D12, D13) | `check_individual_item_cif_ceiling` (l.102) | Implemented; limitation: ignores payload allotments |
| Create/update save order | D7 null-date check, then ceiling under lock, then header, allotments, rows | `save_boe_with_rows` (l.1284), `_create_boe` (l.1315), `_update_boe` (l.1342) | Moved from serializer in B3; order copied verbatim per reviewer |
| Allotment M2M | Replace only when list non-empty; is_boe set/cleared when no other BOE links it | `_replace_allotments` (l.1394) | Per reviewer reading |
| ProtectedError on update | Savepoint, 400 response, rollback; logged server-side | `_delete_orphan_rows` (l.1463-1480) | Logger name changed (see open items) |

## Cross-checks

- `boe_service.py` imports `apps.license.services.effective_cif_mode` (same edge serializers had). Architecture test passed.
- Architecture ratchet: `('bill_of_entry','serializers','RowDetails')` baseline 4 to 0 (entry removed in `backend/tests/architecture/test_architecture.py`).
- Reviewer B3: approve by reading the diff line by line. Reviewer did NOT run tests. Opus review of `_upsert_rows` ordering/locking was requested by implementer; not yet confirmed as done.

## Data facts (local, read-only)

- 1044 BOEs; 1015 have frozen rows; 159 legacy OTH BOEs protected by D6.
- Read-only echo validation: 0 false 400s across 1044.

## Open items

| # | Item | Severity |
|---|---|---|
| 1 | Opus/CIF-auditor review of `_upsert_rows` against old branches (requested, not confirmed) | Required before merge |
| 2 | Add API tests for: id not on this BOE (falls to update_or_create), frozen row echoed with id (kept), orphan delete ProtectedError rollback | Low (paths match old code by reading) |
| 3 | INDIVIDUAL_ITEM ceiling ignores payload allotments | Documented limitation |
| 4 | Merge-path `update_fields` persistence and refresh-on-commit: verify per D4 | Confirm in final gate |
