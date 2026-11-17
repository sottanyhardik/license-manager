# BOE modernization — approved owner decisions (Iteration 2)

Approved by the product owner in the BOE ERP modernization thread on 2026-11-17
(Iteration 2 master prompt). These supersede the "escalations" list in
`docs/erp-architecture/boe-modernization-progress.md` (items 1–15).

Still frozen (not changed by these decisions): canonical CIF rule
(`.claude/rules/business-rules.md`), the `LicenseBalanceCalculator` engines,
A-2 (`calculate_balance.py` hidden-BOE handling of stored quantity), Total Allotted.
Balance *refresh* triggers may be added; balance *math* may not change.

| # | Decision | Required behaviour |
|---|---|---|
| D1 | Hidden BOE invoice number | Changing `invoice_no` on a **genuinely hidden** BOE (`genuinely_hidden_boe_ids`) returns HTTP 400 on both `update-invoice-no` and PUT/PATCH; users must use restore/hide. Legacy free-text `OTH` on never-hidden BOEs stays editable. HIDE_BOE / RESTORE_BOE audit records stay correct. |
| D2 | BOE_VIEWER | Read-only with exactly ONE write exception: `POST /bill-of-entries/{id}/update-invoice-no/`. No create/edit/delete/merge/resolve-dispute/update-product-name/bulk/hide/restore/item/allocation/financial writes. Enforced in backend permissions; frontend visibility matches. Positive + negative tests. Do NOT remove the invoice exception. |
| D3 | Frozen rows | Ordinary BOE form updates never delete `RowDetails.is_frozen=True` rows, even if omitted from the payload. Regression tests. |
| D4 | Merge integrity | Frozen BOE has priority regardless of input order. A: one frozen → frozen BOE survives; eligible rows from the other move in; frozen rows never deleted/overwritten/modified (ids, values, references, audit kept). B: both frozen → preserve both sets if constraints allow, else reject with a clear validation error. C: neither → existing rules. All cases: lock both, persist exchange rate, validate hidden-state compatibility (reject when exactly one is genuinely hidden), prevent duplicate merges, atomic, identify all affected licences/items, refresh canonical balances on commit, full audit. Tests for every case in both input orders. Independent CIF-auditor review. |
| D5 | Old/new refresh on row move | Moving RowDetails between licences/items: capture old relationships before mutation; refresh old+new licence and old+new item; no duplicate refresh when unchanged; correct transaction/on_commit handling. CIF-auditor approval. No change to A-2 logic. |
| D6 | Restore collision | Restore uses genuine-hidden audit history (`genuinely_hidden_boe_ids`); never infer hidden from `invoice_no == 'OTH'`; never erase a legitimate `OTH` invoice. |
| D7 | Upsert contract | Reject ambiguous create/update with a missing date where an existing record could be overwritten or duplicated: structured HTTP 400, include existing-record reference (id) where safe/authorized. Keep the DB uniqueness contract. No migration without data analysis. |
| D8 | Allotment lookup | `fetch-allotment-details`: invalid id → 400, unknown → 404, valid → unchanged success contract. |
| D9 | PDF parsing | `create_company=false` by default; creating companies requires explicit company-write permission and the MDS write gate; no raw exception text to clients; keep server-side logs. |
| D10 | PDF upload + copy name | User-facing copy filename `BOE_<BOE_NUMBER>_<BOE_DATE>.pdf` (e.g. `BOE_1234567_15-11-2026.pdf`), sanitized. Validate PDF signature/content, configurable size limit, reject malformed, prevent path traversal, safe storage paths, no executable/HTML, safe Content-Disposition. Internal storage may use unique ids. Missing number/date → validation error (never invent identifiers). Do not delete historical files; preserve existing references. |
| D11 | Workspace UX | Overview default tab; remove Edit Options only after action parity; consolidate actions in shared ActionMenu; mount ConfirmProvider; keep role gating; protect destructive ops. |
| D12 | M2M + INDIVIDUAL_ITEM | Characterize first. Fix BOE–allotment M2M link/unlink recalculation, old/new relationship refresh, INDIVIDUAL_ITEM CIF ceiling, own-debit adjustment on edit. CIF-auditor review. |
| D13 | INDIVIDUAL_ITEM own debit | An unchanged row must not fail because its own debit is counted twice. Test unchanged, increased, decreased, licence change, item change, multiple rows, concurrent modification. |
| D14 | planning_target_item | Preserved on PATCH where supported; explicit validation + persistence; API regression tests. |
| D15 | Numeric-string ids | Keep numeric-string id compatibility for bulk hide/restore (Iteration 1 fix). |
