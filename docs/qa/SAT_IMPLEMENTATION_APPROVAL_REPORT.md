# SAT Implementation Approval Report (gate — awaiting owner approval)

Date 2026-11-20 · branch `feature/v5` @ `ec3604cb` · **no code changed.** Decisions: `SAT_USER_DECISION_REGISTER.md`
(the "SAT decision closure" section and the question log). Defects: `SAT_DEFECT_REGISTER.md`. Every item below is a
**BUSINESS-RULE, API CONTRACT, SCHEMA or PERMISSIONS change**, flagged per workstream. Nothing starts before explicit
owner approval of this report. Data repairs need a **second, separate** approval after a dry-run list.

## 1. Decisions

**Approved (owner, 2026-11-20):** DEC-11 B · SAT-DEF-102 B (= DEC-12) · SAT-DEF-120…132 A · SAT-DEF-150 A (C-2: auto-link
exact matches + review) · DEC-50 D (C-3: any item on the licence, CIF only) · SAT-DEF-140 D (C-4: USD, null ≤ 100) ·
RC3/RC13 C · DEC-01 A · DEC-03 C · DEC-04 A · DEC-05 keep · DEC-06 A · DEC-07a A · DEC-07b A · DEC-08 merge within
licence · DEC-09 A · DEC-10 A · DEC-13 A · DEC-14 B (short BOE releases the remainder) · DEC-20/23 max(invoice, BOE) +
flag (C-1 superseded) · DEC-24 C credit note · DEC-25a tonnes · DEC-25b A · DEC-25c A · DEC-26 C estimate · DEC-51 A ·
SAT-DEF-142/151 B · DEC-30 A · DEC-31 A · DEC-32 C · DEC-33 A · DEC-34 B · DEC-35 A · DEC-36 A · DEC-37a A · DEC-37b C ·
DEC-38a A · DEC-38b A · DEC-39a A · DEC-39b B · DEC-40 B.

**Derived, stand unless the owner objects:** DEC-02, DEC-60 (from C-2) · DEC-25d (from DEC-25b).

**Deferred:** none from the owner. Still pending: the CA items (GST, TDS, costing) and the Tally cut-over, which are outside SAT.

### Points to confirm at the gate (design, or possible conflicts with earlier decisions)

| # | Point | Proposal |
|---|---|---|
| G1 | **DEC-50 A vs D-A / D-C.** D-C rejects allotments above the %-pool cap. DEC-50 A lets any item cover another's CIF over-use. Do adjustments ever raise an item's allotment cap, or only absorb over-use that has already happened? | Adjustments only absorb realised over-use (debits). Allotment caps (D-B / D-C) are unchanged. **Owner confirms** |
| G2 | **DEC-14 B, retroactive?** Does it apply to existing partially covered allotments? | Yes, computed at read time (no row writes). Dry-run list of affected allotments and CIF first |
| G3 | **C-2 exact-match tolerance** | qty equal at 3 dp, CIF equal at 2 dp, same licence + import item + company |
| G4 | **DEC-26 price source** | Licence import-item rate (item CIF ÷ licensed qty), else the unit-price master. Computed at read time, not stored |
| G5 | **DEC-11 snapshot storage** | Keep the plan-time figures in a new read-only audit table; the operative figures are live |
| G6 | **DEC-24 credit-note design** | New trade credit-note type linked to the original trade line, partial allowed, reverses qty/CIF per line |
| G7 | **DEC-32 deprecation period** | 60 days; `/api/payments/` POST returns a JSON 4xx meanwhile |
| G8 | **DEC-23, multiple invoices/BOEs on one item** | max(Σ linked invoice qty, Σ linked BOE qty) per item and link group |

## 2. Workstreams (proposed order; one owner per file)

| WS | Scope | Decisions / defects | Main files | Flags |
|---|---|---|---|---|
| **0** | Characterisation tests pinning current behaviour, before any change | all | `apps/*/tests/` | — |
| **1 Engine (financial-integrity owner, single agent, sequential)** | AR at item level · rowless-BOE link stays outstanding + exception · COMMISSION excluded · disputed flag · RELEASED honoured · short-BOE remainder release · exact auto-link + review queue · DEC-50 cross-item CIF adjustment (audited) · DEC-51 eligibility · SAT-DEF-005 cap (D-A) | DEC-01, 03, 06, 07a/b, 14, C-2, 50, 51; SAT-DEF-001…007, 150 | `license/services/balance_calculator.py`, `core/scripts/calculate_balance.py`, `reconciliation/*`, `allotment` models | BUSINESS-RULE, SCHEMA |
| **2 Quantity** | max(invoice, BOE) + mismatch flag · blank → BOE fallback · missing-qty flag · negative-qty validator · SALE update guard · `allocated_qty=0` fallback · `billed_no_boe_qty` = engine · item-level `qty_comparison` · no swallowed exceptions · duplicate blank invoice no. · DEC-26 estimate · units (list, tonnes, item unit) | DEC-20/23, 21, 22, 25a–d, 26; SAT-DEF-120…132 | `trade/models.py`, `trade_service`, `boe_link_reconciler`, `license.py:451`, PDFs | BUSINESS-RULE, SCHEMA (validator/choices) |
| **3 Planning** | Live plans + audit snapshot · billed-without-BOE in usage · Plan tab = `get_balance_cif` · BOE-converted PLAN stays consumed · netting/DEC-14 · quantize, Decimal | DEC-11…14; SAT-DEF-100…106 | `planning_usage_reconciliation.py`, `plan_enforcement.py`, `api/views/license.py:433-458` ⚠ peer-dirty | BUSINESS-RULE, SCHEMA |
| **4 Stored fields** | Single writer (D-A/D-F) · scheduled + on-change refresh · independent reconciliation command (stored vs canonical, stale report) · recalc/recovery command · API numbers rounded (2/3 dp) · null-DFIA one constant + warning bands | RC3/RC13 C, D-D, D-F; SAT-DEF-140, 141, 142, 151 | `license/signals.py` ⚠ peer-dirty, `serializers/license.py` ⚠ peer-dirty, `item_usage.py` ⚠ peer-dirty | API values (not fields) |
| **5 Exports** | Ledger surfaces = licence balance · Item Pivot numbers/dates · licence list dates · DEC-08 merge per licence · DEC-09 letter subject · Low formatting items | DEC-04, 08, 09; SAT-DEF-010…022 | `license_balance_ledger_builder.py`, `item_pivot_excel.py` ⚠ peer-dirty, `allotment_pdf.py` ⚠ peer-dirty | display |
| **6 Security / permissions** | PROTECT deletes · trade roles read-only licence UI · evidence upload roles · superuser-only grants · per-entity accounting roles · self-approval log/report · role-gated masters/schema/user list · admin-only username · failed-login log + append-only ActivityLog · route deprecation · SAT-DEF-050, 052, 054–061, 063, 064 · untrack `.env*` | DEC-30, 32, 34–40 | `accounts/permissions.py`, `media.py`, `ledger.py`, accounting, frontend nav | PERMISSIONS, SCHEMA, API CONTRACT |
| **7 Credit note** | Trade credit note (G6) | DEC-24 | `apps/trade` | SCHEMA, BUSINESS-RULE |
| **8 Performance** | BOE list N+1, licence detail queries, item-report pagination, allotment list, Redis `IGNORE_EXCEPTIONS` | SAT-DEF-030, 032–034, 039 | views/serializers | — |

WS1 → WS2 → WS3 → WS4 run sequentially (shared formulas). WS5, WS6 and WS8 can run in parallel worktrees (disjoint
files). Five target files have **uncommitted peer edits** (marked ⚠). They are coordinated with their owner before
editing and never overwritten.

## 3. Database migrations (expected; reviewed by `migration-safety`, all reversible, run on test DBs only)
- Allotment↔BOE link audit (batch id, match type exact/reviewed, user, timestamp) — C-2.
- Item CIF adjustment record (licence, source item, destination item, amount, timestamp, reason, batch) — DEC-50.
- Plan snapshot/audit table — DEC-11.
- Trade line qty validators (non-negative) and unit choices — SAT-DEF-121, DEC-25b. Existing negative rows are checked first; the constraint is added only if none exist.
- FK `on_delete` → PROTECT on company/port references — DEC-30.
- Role↔entity assignment — DEC-37a. Failed-login / append-only audit fields — DEC-39a. Trade credit note — DEC-24.
- The local `lmanagement` DB still lacks `license.0067`. Migrating it is the owner's step.

## 4. Data repair (each needs its own approval after a dry-run list; none runs with the code deployment)
1. First C-2 auto-link run over existing data (exact matches; the review queue for the rest).
2. Stored-field cache refresh on `lmanagement` (writes the cache columns only).
3. Owner/UI work, no script: DEC-33 junk licences, the SAT-DEF-003 duplicate BOE 8391561, SAT-DEF-128/129 data review, the review queue from item 1.
4. Untrack the `.env*` files (a commit).

## 5. Risks
- **DEC-14 B:** a later BOE on a released allotment can push a licence over-utilised after planning has used the released CIF. It is surfaced as a reconciliation exception, never hidden.
- **DEC-50 A:** value can move out of an item with its own DGFT value cap (owner accepted). Statutory records are untouched, and every adjustment is audited and reversible by batch.
- **DEC-20/23 max rule:** item qty may exceed the customs debit where the invoice qty is larger. Each mismatch is flagged.
- **C-2:** a false exact match releases a reservation. Mitigated by the strict tolerance (G3), the audit batch and a one-click reversal.
- **DEC-11:** saved plan figures users have seen will change. The historical snapshot stays visible.
- **Performance:** live recalculation must use bulk maps (no N+1), measured before and after.
- **Peer overlap:** 180 dirty paths in the shared tree.

## 6. Test requirements
Characterisation tests first, then targeted tests per change, then the area gate, then a full `quality-gate.sh backend|frontend` once
per integration. These cover the scenario list in the SAT brief §8: invoice qty present, blank or 0; BOE match or none; multiple
invoices per BOE; partial BOE and allotment; hidden BOE; over-utilised item with and without surplus; duplicate invoice
or BOE; cancellation by credit note; edit, delete, reverse, restore; negative CIF; null-DFIA at 100, 100.01, 101,
200, 200.01, 201, 500, 500.01, 501 USD. Also concurrency on the link and adjustment writers, migration forward and
backward tests, the stored-vs-canonical reconciliation command on the test DB, and a role-matrix rerun. Each runner uses
its own `TEST_DB_NAME`. Independent reviews: `cif-balance-auditor` (Opus) for WS1–4, `boe-reconciliation-auditor` for
C-2/DEC-14, `invoice-auditor` for WS2/7, `security-auditor` for WS6.

## 7. Rollback
One small commit per decision, so each can be reverted alone. Every migration is reversible (new tables and fields
only, nothing dropped). Link and adjustment writes carry a batch id, and a management command reverses a batch.
Data repairs run only after a `pg_dump` of the affected tables, kept under `~/lm_backups/`. The stored-field cache can
always be rebuilt from canonical transactions.

**STOP.** Approval needed for: (1) this plan and workstream order, (2) G1–G8, (3) starting WS0+WS1. Data repairs are
approved separately later.

## Owner approval — 2026-11-20
"approved, G1 as proposed, start WS0 and WS1". The plan and workstream order are approved; G1 is approved as proposed
(adjustments absorb only realised over-use, allotment caps unchanged); G2–G8 are approved as proposed. Authorised:
WS0 + WS1. Data repairs (§4) and commits/push are **not** covered and need separate approval.
