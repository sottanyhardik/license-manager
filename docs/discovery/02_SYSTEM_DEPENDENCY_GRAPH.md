# System Dependency Graph — License Manager
**Discovery Date:** 2026-08-10  
**Method:** Code import analysis, model relationships, view call chains  
**Validation:** Verified against 1,072 files, 6,245 symbols, 141–25 dependent ranges

---

## DEPENDENCY HIERARCHY

```
┌─────────────────────────────────────────────────────────────┐
│                       USERS (Browser)                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                    React SPA Frontend
                    ├─ React Router
                    ├─ Pages (40+ routes)
                    ├─ Components (50+ components)
                    ├─ API Hooks
                    └─ State (AuthContext, Theme)
                             │
                             │ HTTPS → /api/*
                             │
┌────────────────────────────────────────────────────────────┐
│                    Django REST API                          │
├────────────────────────────────────────────────────────────┤
│ Permissions → Views/ViewSets → Serializers → Services      │
└───────────────────────┬──────────────────────────────────┘
                        │
            ┌───────────┼───────────────────────┬────────┬─────────┐
            │           │                       │        │         │
      ┌──────────┐  ┌──────────┐  ┌─────────────┐  ┌──────────┐  ┌────────────┐
      │ License  │  │ Allotment│  │ BOE/Invoice │  │ Recon.   │  │ Reports    │
      │ (Module2)│  │ (Module6)│  │ (Module7-8) │  │ (Module9)│  │ (Module10) │
      └────┬─────┘  └─────┬────┘  └────────┬─────┘  └────┬─────┘  └────┬───────┘
           │              │               │             │           │
           │              └───────────────┼─────────────┘           │
           │                              │                         │
    ┌──────┴──────────────┬───────────────┤                         │
    │                     │               │                         │
┌───────────────────┐ ┌──────────────┐ ┌─────────────┐  ┌────────────────┐
│ License Ledger    │ │ License      │ │ Allocation  │  │ Reconciliation  │
│ (Module3)         │ │ Planning     │ │ Ledgers     │  │ Ledgers         │
│                   │ │ (Module5)    │ │ (Module9)   │  │ (Module9)       │
│ - build_dfia...   │ │              │ │             │  │                 │
│ - build_incentive │ │ - E1 planner │ │ - Invoice   │  │ - InvoiceBOE    │
│                   │ │ - E5 planner │ │   BOEAlloc  │  │   Allocation    │
│ Depends on:       │ │ - A3627      │ │ - BOE       │  │ - BOEAllotment  │
│ - LicenseBalance  │ │ - Milk       │ │   Allotment │  │   Allocation    │
│ - ExportItems     │ │              │ │   Alloc     │  │ - ExternalInvoi │
│ - RowDetails      │ │ Depends on:  │ │ - External  │  │   ceLink        │
│ - Trades          │ │ - Condition  │ │             │  │                 │
│                   │ │   Pool       │ │ Depends on: │  │ Depends on:     │
│ ↓                 │ │ - Item       │ │ - RowDetails│  │ - InvoiceBOEAll │
│ PDF/Excel         │ │   Matcher    │ │ - Allotment │  │   ocation       │
│                   │ │ - Plan       │ │   Items     │  │ - BOEAllotment  │
└───────────────────┘ │   Grouping   │ │ - LicenseTr │  │   Allocation    │
                      │              │ │   adeLine   │  │ - ExternalInvoi │
                      └──────────────┘ │             │  │   ceLink        │
                                       └─────────────┘  │ - ReconciliationLog
                                                       │ - IgnoredWarning
                                                       └────────────────┘
                                       │
                   ┌───────────────────┤
                   │                   │
            ┌──────────────┐   ┌──────────────┐
            │ License      │   │ Core         │
            │ Balance      │   │ (Foundation) │
            │ (Module4)    │   │ (Module1)    │
            │              │   │              │
            │ - Balance    │   │ - Auth       │
            │   Calc       │   │ - Master     │
            │ - Condition  │   │   Data       │
            │   Pool       │   │ - Utilities  │
            │              │   │ - Perms      │
            │ Depends on:  │   │              │
            │ - ExportItem │   │ Depended on  │
            │ - ImportItem │   │ by: ALL      │
            │ - RowDetails │   │ modules      │
            │ - BOE        │   │              │
            │ - Allotment  │   │ (141 + 121   │
            │ - Trade      │   │ dependents)  │
            │              │   │              │
            │ 43 dependents│   │              │
            └──────────────┘   └──────────────┘
```

---

## CRITICAL DEPENDENCIES

### Tier 0: Foundation (Everything Depends On This)

**`backend/apps/core/models.py`** (121 dependents)
- `CompanyModel` — 9+ PROTECT references (deletion dangerous)
- `PortModel` — 4+ PROTECT references
- `ItemNameModel` — M2M references across license items
- `SionNormClassModel` — Planning/export structures
- `ExchangeRateModel` — Financial calculations
- **Risk:** Cannot delete without careful migration
- **Change Impact:** MASSIVE (all modules affected)

**`backend/apps/accounts/permissions.py`** (30 dependents)
- 10+ permission classes
- Every view depends on this
- **Risk:** Changes affect all API endpoints
- **Change Impact:** HIGH (auth changes break all views)

**`backend/apps/core/constants.py`** (53 dependents)
- Constants referenced across all modules
- **Change Impact:** MEDIUM

---

### Tier 1: License/Core Domain (Primary Business Logic)

**`backend/apps/license/models/__init__.py`** (141 dependents)
- Exports all license models
- Depended on by: allotment, bill_of_entry, trade, reconciliation, license views/services
- **Risk:** Extremely high refactor risk
- **Change Impact:** MASSIVE

**`backend/apps/license/services/balance_calculator.py`** (43 dependents)
- HOTTEST PATH
- Called by: all balance views, ledger, reports, planning, reconciliation
- **Risk:** Changes to balance formula break:
  - License list views (balance display)
  - Ledger views (balance calculation)
  - Reports (all reports use balance)
  - Planning (plan cap validation uses available balance)
  - Reconciliation (BOE debit uses balance)
- **Change Impact:** CRITICAL (affects every module)

**`backend/apps/license/services/plan_grouping.py`** (13 dependents)
- Item grouping for all planners (E1, E5, E126, E132, A3627)
- **Risk:** Changes to grouping key affect planning allocation across all SION norms
- **Change Impact:** HIGH

**`backend/apps/license/signals.py`** (13 dependents)
- Updates license flags on item/allotment/BOE changes
- **Risk:** Disabling signals breaks balance consistency
- **Change Impact:** MEDIUM

---

### Tier 2: Transaction Ledgers (Complex Multi-Model)

**`backend/apps/bill_of_entry/models.py`** (46 dependents)
- `BillOfEntryModel` — referenced by:
  - License balance calc (debit tracking)
  - Trade (BOE linking)
  - Reconciliation (allocation ledgers)
  - Reports (ledger display)
- **Risk:** BOE deletion cascades through RowDetails → allocation ledgers
- **Change Impact:** HIGH

**`backend/apps/allotment/models.py`** (44 dependents)
- `AllotmentModel` referenced by:
  - Balance calc (allotment deduction)
  - BOE (M2M linking)
  - Reconciliation (allocation ledgers)
  - Reports (allotment display)
- **Risk:** Allotment deletion cascades through items → impact on balances
- **Change Impact:** HIGH

**`backend/apps/trade/models.py`** (36 dependents)
- `LicenseTrade` referenced by:
  - Balance calc (trade debit/credit)
  - BOE linking (stamp invoice_no)
  - Reconciliation (allocation ledgers)
  - Reports (trade display, profit calc)
- **Risk:** Trade deletion affects balance calculation
- **Change Impact:** MEDIUM-HIGH

**`backend/apps/reconciliation/models.py`** (25 dependents)
- Three allocation ledgers (InvoiceBOEAllocation, BOEAllotmentAllocation, ExternalInvoiceLink)
- PROTECT relationships on row_details (immutable audit trail)
- **Risk:** High (PROTECT prevents deletion, ledger records must be preserved)
- **Change Impact:** MEDIUM

---

## DATA FLOW CHAINS

### License → Balance → Planning → Allotment → BOE → Invoice/Trade → Reconciliation → Reports

**Create License**
```
License created
  ↓ (signal)
Create LicenseBalance (OneToOne, CASCADE)
Create LicenseExportItem/ImportItem (CASCADE)
  ↓ (populate default balances)
balance_cif = calculate_financial_balance() [service call]
available_quantity = quantity [model save]
```

**Allocate to Allotment**
```
Create AllotmentItem (links ImportItem)
  ↓ (signal: post_save AllotmentItems)
Recalculate ImportItem balance:
  - allotted_quantity = SUM(AllotmentItems.qty)
  - available_quantity = quantity - allotted - debited
  ↓ (cascade up)
Update LicenseBalance.balance_cif [recalc on demand]
```

**Create BOE/RowDetails**
```
Create RowDetails (BOE line item)
  ↓ (signal: post_save RowDetails)
Recalculate ImportItem balance:
  - debited_quantity = SUM(RowDetails[DEBIT].qty)
  - available_quantity = quantity - allotted - debited
  ↓ (cascade up)
Update LicenseBalance.balance_cif [recalc on demand]
```

**Create Trade (Invoice)**
```
Create LicenseTradeLine (links ImportItem + SR)
  ↓ (optional: link to BOE via boes M2M)
  ↓ (stamp BOE.invoice_no if linked)
  ↓ (create/update InvoiceBOEAllocation ledger)
Reconciliation queries detect mismatch
```

**Create Allocation Ledger**
```
POST /api/reconciliation/link/ (requires both BOE_MANAGER + TRADE_MANAGER)
  ↓
Create InvoiceBOEAllocation (PROTECT on row_details, trade_line)
  ↓
Debit recalculation [allocation-driven]:
  - BOE row contributed debit = max(cif - allocated, 0)
```

**View Ledger/Report**
```
GET /licenses/{id}/ledger_detail/ [LicenseLedgerViewSet]
  ↓
Call build_dfia_ledger_detail() [backend builders]
  ↓
Calculate running balance per row:
  - Option A (backend): license-wide, PURCHASE→SALE order
  - Option B (frontend): per-company, restarts per company
  ↓
Return JSON
  ↓
Frontend: render, PDF export (jsPDF), Excel export (ExcelJS)
  ↓ (all three use different balance convention — P0 defect)
```

---

## COUPLING ANALYSIS

### High Coupling (Refactor Risk: EXTREME)

**Balance Calculation ↔ Everything**
- 43 dependents directly call balance_calculator
- Changes to balance formula ripple through:
  - License views (balance display broken)
  - Planning views (plan cap broken)
  - All reports (totals change)
  - Reconciliation queries (debit calculation broken)
- **Mitigation:** Add golden-data regression tests BEFORE any change

**License Models ↔ All Modules**
- 141 dependents
- License is the central entity
- Changes to fields/relationships affect: views, serializers, services across 8 apps
- **Mitigation:** Model changes require database migration, schema review, dependent code audit

**Core Master Data ↔ All Modules**
- 121 dependents
- Company, Port, HS Code, SION norms referenced everywhere
- Deletion of master data requires PROTECT constraints (implemented recent commit b3802917)
- **Mitigation:** No more CASCADE on master data

### Medium Coupling (Refactor Risk: HIGH)

**BOE ↔ Balance ↔ Reports**
- BOE line items feed debit tracking in balance calculation
- Balance feeds all reports
- Changes to BOE structure require balance calculator changes
- **Mitigation:** Treat as single refactor unit (BOE + Balance)

**Planning ↔ Balance ↔ Validation**
- Planning service validates against available balance
- Available balance depends on allocation (which depends on planning)
- Circular dependency (benign: validated at API level)
- **Mitigation:** Separate validation concerns into dedicated service

**Reconciliation ↔ Balance**
- Reconciliation ledgers track allocations used to calculate balance
- Circular dependency (PROTECT constraints prevent loops)
- **Mitigation:** Treat reconciliation ledgers as immutable audit trail

### Low Coupling (Refactor Risk: LOW)

**Allotment** — relatively isolated
- Depends on: License (balance), Core (master data)
- Depended on by: Balance, BOE, Reports
- **Mitigation:** Can be refactored independently if balance/BOE interfaces stable

**Trade** — moderately isolated
- Depends on: License (balance), Core, BOE (linking)
- Depended on by: Balance, Reconciliation, Reports
- **Mitigation:** Can refactor independently with balance/BOE interface contracts

---

## CIRCULAR DEPENDENCIES

**Planning ↔ Planning Validation**
```
Available Balance
  ↓
Plan Validation [checks: planned_qty <= available]
  ↓
Available Balance [recalc] [circular, benign]
```
**Resolution:** Breaks at API boundary (400 error if cap violated). Safe.

**Reconciliation ↔ Balance**
```
BOE Debit Calculation
  ↓ (depends on)
Allocation Ledger [InvoiceBOEAllocation]
  ↓ (fed by)
Reconciliation Service
  ↓ (depends on)
Balance Available
```
**Resolution:** PROTECT constraints prevent deletion loops. Safe.

---

## MISSING DEPENDENCIES (Architectural Debt)

### Balance Calculation Should Depend On:
- ✅ ExportItems (currently does)
- ✅ ImportItems (currently does)
- ✅ RowDetails (currently does)
- ✅ AllotmentItems (currently does)
- ⚠️ Allocation Ledgers (currently does, but could be more explicit)
- ❌ Hidden BOE Marker (currently implicit, should be explicit)

**Recommendation:** Make hidden BOE logic explicit in balance calculator (currently hides BOEs if latest ReconciliationLog.action = HIDE_BOE, but no comment)

### Reports Should Depend On:
- ✅ Balance (currently does via balance_calculator)
- ✅ Ledger builders (currently does)
- ⚠️ Allocation ledgers (used but not explicit in queries)

**Recommendation:** Document which reports depend on which allocation ledgers

---

## REFACTOR SEQUENCE (Dependency-Driven)

1. **Core/Foundation** (no dependencies, depended on by 141+121)
   - Locked: Do not refactor before other modules
   
2. **License Models** (141 dependents)
   - Locked: Refactor only after establishing firm contracts with dependents

3. **Balance Calculator** (43 dependents, hot path)
   - CANDIDATE for performance optimization
   - REQUIRES: golden-data regression tests before change

4. **Planning** (13+ dependents via plan_grouping)
   - CANDIDATE for new A3627 validation
   - REQUIRES: Unit tests for A3627 planner before refactoring

5. **BOE + Allotment** (46+44 dependents)
   - Can refactor in parallel with minimal impact
   - REQUIRES: balance_calculator stability

6. **Trade** (36 dependents)
   - Can refactor independently
   - REQUIRES: BOE linking interface stability

7. **Reconciliation** (25 dependents, complex)
   - Can refactor independently (PROTECT constraints isolate)
   - REQUIRES: Allocation ledger API stability

8. **Reports** (driven by all above)
   - Last to refactor
   - DEPENDS on: all 6 modules above stable

---

## CHANGE IMPACT PREDICTIONS

### If Balance Calculation Changes:
- ❌ ALL reports recalculate totals
- ❌ ALL license list views show different balances
- ❌ Planning views break (plan cap changes)
- ❌ Reconciliation queries recalculate debits
- **RISK:** CRITICAL (all users see different numbers)
- **MITIGATION:** Golden-data test must verify all consumers

### If BOE Model Changes:
- ⚠️ Balance calculation affected (if debit tracking changed)
- ⚠️ Reconciliation queries affected (if row structure changed)
- ⚠️ Reports affected (if display data changed)
- **RISK:** HIGH
- **MITIGATION:** Contract tests on balance_calculator + reconciliation queries

### If License Models Change:
- ❌ ALL modules affected (141 dependents)
- ❌ ALL views/serializers/services affected
- ❌ Database migration required
- **RISK:** CRITICAL
- **MITIGATION:** Never refactor in isolation (coordinate with all 10 dependent modules)

---

## SUMMARY

The system is **moderately coupled** with a clear **critical path:**

```
Core Foundation
  ↓
License
  ↓
Balance (Hot Path)
  ↓
Planning / Allotment / BOE
  ↓
Trade / Reconciliation
  ↓
Reports
```

**Refactor Order:** Bottom-up (Reports first, Foundation last).

**Highest Risk:** Balance calculator (43 dependents, complex, hot path, no golden-data parity).

**Quick Wins:** Allotment, Trade (low coupling, stable interfaces).

**Locked Until Tests:** Balance calculator, Planning (A3627), Reconciliation (ledger integrity).
