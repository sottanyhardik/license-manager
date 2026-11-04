# License Ledger — Phase 2 Checkpoint

**Verdict: NOT READY FOR DEPLOYMENT.** Work is checkpointed, not complete.

## Baseline (verified this cycle)

- Branch `feature/version-4`; 123 uncommitted entries in the working tree. The License Ledger work is a subset.
- Golden snapshot `/tmp/golden_baseline_locked.json` (read-only): 779,231 bytes, SHA-256 `a6d58a75b515afdc`, 80 licences. Unchanged, never regenerated.
- Django `manage.py check`: no issues. `makemigrations --check`: no pending migrations.
- Repository-wide blockers outside the Ledger (not repaired here):
  - `sion_planning_execution.py` and `seed_browser_2509.py` carry pre-existing uncommitted changes. Two tests (`test_split_by_percent_zero_availability…`, `test_seed_browser_2509…`) pass on clean HEAD and fail in the working tree.
  - Ten further backend failures reproduce on clean HEAD (item-pivot, a3627 Excel, E1/E132 Excel ordering, allotment plan-mode, overview summary).
  - `test_parse_pdf_hs_autocreate.py` collection error (missing `SAMPLE_PDF_DATA` in conftest). Not checked against HEAD.

## Completed and verified this cycle

| Item | Evidence |
|---|---|
| Adapter identity (`canonicalLedgerAdapter.js`) sends `license_type` when known | `canonicalLedgerAdapter.test.ts` (3 tests) |
| Touch targets at 390 px: row checkboxes wrapped in 24 px labels; Ledger/PDF actions and chip remove buttons at least 24 px | Browser measurement: 115 small targets reduced to 4 of 223. The 4 remaining are react-select cursor inputs inside 36 px controls. |
| `td-has-header` on the 7 SION tables: missing header for the actions column | Added a screen-reader "Actions" header. The Lighthouse audit now passes. |
| Contrast: grand-total bar moved off brand blue (2.55:1 in dark theme) to `bg-muted`; layout brand line uses full secondary text colour | Lighthouse dark theme: ledger contrast nodes 8 → 0 in ledger scope. Light theme: 0. |
| Accessible names: "Preview PDF" and "Download Excel" contain their visible text | Lighthouse: label mismatches 3 → 1 |
| Browser Excel download | Real click. Request `/api/license-ledger/export/?…&file_format=xlsx` returned 200 with the page's filters and no paging parameters. Saved file `license-ledger (11).xlsx`: sheets `License Summary` (135 rows) and `Financial Trade Ledger` (329 rows). GRAND TOTAL row = 6094850.51 / 65019355.06 / 64362156 / −657199.06, matching canonical totals. |
| Browser PDF request | Real click. Export request returned 200 with the same filters. The PDF opens in a new tab and was not saved, so its content is **not** verified in this cycle. |
| Frontend suite | 115 files, 993 of 993 pass. TypeScript 0. ESLint 0 on changed files. `vite build` 0. |

Lighthouse accessibility, light theme: score 100, with one failing audit (`label-content-name-mismatch`) on the shared top-navigation search button, whose visible text is split by a `⌘K` key element.

## Not completed (remaining acceptance gates)

1. **Table and filter redesign.** Not started beyond the fixes above.
2. **Accessibility residuals.** Dark theme: "License Downloads" and "Clear All" outline buttons, and the shared "New License" footer action, fail contrast. The shared `Button` outline variant and the footer token resolve to light surfaces in dark mode. Light theme: the shared nav search button name. Both need design-token or shared-component work outside the Ledger page.
3. **Permanent financial equivalence fixtures.** The existing gate covers trades, an empty licence, and an identifier collision. BOE, allotment, transfer, billed-without-BOE, over-allocated and unmapped scenarios are not yet fixture-tested. The golden snapshot is the only coverage for those.
4. **Metrics-builder optimisation review.** Not measured in this cycle.
5. **Browser PDF content and print preview.** PDF content and A4 print layout not inspected in the browser.
6. **Independent reviews.** Not run in this cycle. The earlier React review is superseded by these changes.
7. **Final backend regression.** Not re-run in this cycle. Last measured: 3,482 passed, 12 failed, 1 collection error (see blockers above).

## Files changed in this cycle (License Ledger scope)

- Frontend: `src/pages/LicenseLedger.tsx`, `src/pages/LicenseLedger.test.tsx`, `src/pages/LicenseLedger.pagination.test.tsx`, `src/pages/LicenseLedgerDetail.tsx`, `src/pages/LicenseLedgerDetail.test.tsx`, `src/components/ActiveFilters.tsx`, `src/components/DebouncedSearchInput.tsx`, `src/components/TopNav.tsx` (aria name only), `src/layout/AdminLayout.tsx` (brand-line contrast only), `src/utils/canonicalLedgerAdapter.js`, `src/utils/canonicalLedgerAdapter.test.ts` (new).
- Documentation: `docs/09-module-implementation/ledger-phase2-checkpoint.md` (this file). Screenshots from earlier cycles are in `docs/09-module-implementation/evidence/`.

Shared components touched (`ActiveFilters`, `DebouncedSearchInput`, `TopNav`, `AdminLayout`) changed only additively or by class or label value. Their consumers still pass the full frontend suite.

## Exact next commands

```bash
cd frontend && npx vitest run && npx tsc --noEmit -p . && npx vite build
cd ../backend && ../.venv/bin/python -m pytest apps/license/tests/test_license_ledger_*.py apps/license/tests/test_canonical_ledger_batch_equivalence.py -q -p no:cacheprovider --no-cov
shasum -a 256 /tmp/golden_baseline_locked.json   # must start a6d58a75b515afdc
```

## Rollback

All Ledger changes are uncommitted. Roll back by reverting the file list above individually. Never run `git reset` or `git clean`, which would also discard other owners' work. No migrations, data or configuration were changed in this cycle.
