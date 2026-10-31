# Current-system application inventory

## Evidenced modules

| Domain | Current evidence | Verification status |
|---|---|---|
| Accounts/core | Django account, company, master-data and audit concepts | PARTIALLY_CONFIRMED |
| Licence | Licence details, import/export items, balance/flags/ownership/documents/transfers | PARTIALLY_CONFIRMED |
| Planning/allotment | Allotment and SION planning/rule services | PARTIALLY_CONFIRMED |
| BOE | BOE headers, row details, imports and allocation links | PARTIALLY_CONFIRMED |
| Trade | Trade lines, commercial invoices/payments and allocation links | PARTIALLY_CONFIRMED |
| Reconciliation | BOE/invoice operational matching, issue/disposition concepts | PARTIALLY_CONFIRMED |
| Tasks/integrations | Task application and master-data integration references | PARTIALLY_CONFIRMED |
| Accounting | Commercial transaction concepts; no full GL/bank domain identified | PARTIALLY_CONFIRMED / gap |

This list is not an assertion of complete source coverage. The `.Codex/index/` evidence source required by repository instructions is absent; complete file/symbol/caller inventory is pending.

## Source-inventory gate resolved

The equivalent repository-maintained `.claude/index/` is available and was generated on 31 October 2026. It reports **1,545 files and 9,867 symbols**, with import and dependent maps. It is accepted as the navigation index for this work because it offers the same indexed symbol/caller evidence expected by the repository instructions. It does not prove runtime coverage and its regex extraction still requires source review for correctness.

Initial index counts: 41 files containing model symbols, 32 files containing view symbols, and 57 recorded dependents of `backend/apps/license/services/balance_calculator.py`. The calculator's high blast radius makes it a protected shared service; no balance formula change is permitted before the rule and migration gates pass.

