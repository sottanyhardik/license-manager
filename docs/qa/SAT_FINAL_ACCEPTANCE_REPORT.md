# SAT Final Acceptance Report — License Manager ERP

Date 2026-11-20 · branch `feature/v5` @ `ec3604cb` + peer-owned uncommitted work. **No application code was changed by the SAT**:
no commit, push, migration on real data, fix, or business-rule change. Tree diff hash `6f1712e03000` at the start; later changes
came only from docs/QA files (newest application-source mtime 14:01, before the SAT began).
Evidence root: `~/lm_sat_evidence/` (durable). `/tmp/sat/`, the session-1 evidence, was wiped; its figures survive in the reports and
were re-derived by Phase 9.

## 1. Overall status

**SAT: PARTIALLY COMPLETE.** All nine phases have been assessed and every planned test ID has an outcome. A small set of
executable tests remains NOT-RUN (§9).
**Production readiness: NOT READY.** Three High security defects (privilege escalation and cross-module file access) and four
High financial or export defects are open, none is fixed yet, and the financial results are verified only for licences
**without** trades (0 trades exist in the local data).

Owner decisions: 41 approved entries + 3 derived. They were recorded in another session: the `SAT_USER_DECISION_REGISTER.md`
question log and the `SAT_IMPLEMENTATION_APPROVAL_REPORT.md` §1 list.
**1 open: DEC-41.** Implementation waits on the owner's gate: `SAT_IMPLEMENTATION_APPROVAL_REPORT.md`.

## 2. Phase-by-phase

| Phase | Status | Key numbers (exit codes) | Report |
|---|---|---|---|
| 0 Baseline | PASS | Frontend gate exit 0. Backend: `check` and `makemigrations --check` clean; `pytest tests/` 246 passed; `pytest apps` **4,140 passed, 1 xfailed, exit 0**; flake8/ruff clean | `SAT_EXECUTION_STATE.md` |
| 1 Discovery | PASS-EXC | 375 API paths / 129 view classes. 14 dead frontend clients, 28 orphan endpoints. SAT-ARCH: 4 PASS / 3 PASS-EXC / 2 FAIL | `SAT_API_DATABASE_AUDIT.md` |
| 2 Backend/API | PASS-EXC | SAT-BE: 9 PASS / 5 PASS-EXC / 3 FAIL. Write-path probes 77 run, 70 passed / 7 failed (= findings), exit 1. 0 orphan FKs on 371 columns | same |
| 3 Financial | **PASS-EXC** at licence level, **FAIL** at item level | Licence CIF: independent SQL = engine = APIs on 2,185/2,185; items 26,818 × 6 metrics 0 diffs. FAIL: ARO qty (DEF-001), is_boe without M2M (DEF-002), duplicate BOE (DEF-003) | `SAT_FINANCIAL_AUDIT.md` + peer addendum (4 reports) |
| 4 Integration | PASS-EXC | Browser: BOE debit → balance → screen PASS (2,066.75 → 1,966.75, diff 0.00), reversal PASS, accounting 10/10 and payments 3/3 (exit 0). Allotment-link and invoice↔BOE are blocked in the browser and covered at API level (257 passed / 1 xfailed, exit 0). Licence form writes, transfer and BOE upload NOT-RUN | `SAT_UI_UX_AUDIT.md` + controller addendum |
| 5 E2E | PASS-EXC | 45 pages × 3 viewports = 135 loads: 0 page, console or API errors, 0 overflow. SAT-E2E 19 PASS / 2 PASS-EXC / 1 FAIL / 1 PARTIAL / 3 NOT-RUN. Regression suite 25 passed / 4 failed (test/harness: 401s + login throttle; 1 unclassified) / 16 did not run | same |
| 6 Export | **FAIL** | 25 export families, 19 sample licences. Export tests 192 passed, exit 0. Balance Excel false "FAILED" ledger (DEF-010); bulk Balance Excel overstates on hidden-BOE licences (DEF-070); Item Pivot Excel stores numbers as text (DEF-011) | `SAT_EXPORT_AUDIT.md` |
| 7 UI/UX + security | **FAIL** (security) / PASS-EXC (UI) | Security: 40 IDs, 13 PASS / 14 PASS-EXC / 10 FAIL / 3 NOT-RUN; role matrix 21 principals × 493 route-methods; unauthenticated sweep 0 × 2xx, 0 × 5xx. UI: SAT-UX 5 PASS / 3 PASS-EXC / 6 FAIL (a11y) / 2 NOT-RUN | `SAT_SECURITY_PERFORMANCE.md`, `SAT_UI_UX_AUDIT.md` |
| 8 Performance | PASS-EXC | SAT-PERF 8 PASS / 2 PASS-EXC / 2 FAIL. BOE list N+1: 3,578 queries / 9.5–11 s for 73 rows. Item-report response 65 MB / 230 MB peak. Licence list flat at 16 queries | `SAT_SECURITY_PERFORMANCE.md` (Performance) |
| 9 Independent review | DONE, verdict **ESCALATE-TO-OWNER** | Blind raw SQL: 58/58 sample licences = engine = list API (max diff 0.00); 2,185/2,185 vs bulk engine; Phase 3 totals reproduced to the cent. Reproduced 9 High defects; 1 partial; 1 new High (DEF-070). Pinned balance tests 139 passed, exit 0 | `SAT_INDEPENDENT_REVIEW.md` |

## 3. Module-by-module

| Module | Result | Main findings |
|---|---|---|
| M2 Licence balance (licence level) | **PASS** | Canonical CIF exact on all 2,185 licences across engine, list API and detail API (166 sampled) |
| M2 Licence balance (item level) | **FAIL** | DEF-001 AR qty not deducted (157 items, +40,992,712.93 kg); DEF-005 shared-ceiling cap up to +459,135.24 over the licence; DEF-071 stale stored cache (36 negatives stored as 0.00) |
| M5 BOE | PASS-EXC | DEF-003 duplicate BOE 8391561; 461 unproven identical-row pairs (33.8 M CIF) need a DGFT check; DEF-127/128 data quality; DEF-030 list N+1 |
| M6 Allotments | PASS-EXC | DEF-002 (235,475.75 proven double count); DEF-150 (420,407.75); DEF-004 rowless BOE links; `?is_approved=all` → 500 |
| M7 Reconciliation | PASS-EXC | Cross-licence links (8.13 M) and sibling-item links (8.74 M) need warnings (decided) |
| M8 Trades / invoices | **NOT VERIFIED ON REAL DATA** | 0 trades locally. Test DB: invoice-qty scenarios fail (DEF-120…132, incl. DEF-123 latent qty double count); DEC-41 open. Standalone payments POST → 500 (DEF-031) |
| M9 Accounting | PASS-EXC | Browser suite 10/10. No per-entity scoping (decided: add it, DEC-37a) |
| M4 Planning | PASS-EXC | Planning = engine for BOE CIF on 81 licences; 71/71 ceilings ≤ balance. DEF-102/103 |
| M10/M11 Item Pivot / Item Report | PASS-EXC | Values match the screen. Excel types (DEF-011); 65 MB payload (DEF-034) |
| M13/M14 Ledgers / exports | **FAIL** | DEF-010, DEF-070, DEF-012/013, Low formatting items |
| M15 Masters | PASS-EXC | Export row counts exact; company delete silently NULLs references (DEF-036, decided: block) |
| M16 Auth / users / audit | **FAIL** | DEF-050/051/052 High; DEF-057 tokens survive password change/logout; DEF-058 admin brute force; DEF-062 audit log mutable |
| M17 Jobs / Redis | PASS-EXC | Celery tasks idempotent; dashboard and item-pivot → 500 without Redis (DEF-032) |
| UI shell / a11y | PASS-EXC | 0 runtime errors on 135 loads; accessibility gaps DEF-080…085 |

## 4. Financial discrepancies (affected records)

| Ref | Licence / record | Amount | Status |
|---|---|---|---|
| DEF-001 | 0310825235 item 2393 (+3,838,597 kg); 0310705160 item 2362; 0310831630 item 4281; 157 items / 156 licences | +40,992,712.93 kg; item CIF omits 17,934,272.36 | Decided DEC-01 A, not implemented |
| DEF-070 | 0311002454 (328,985.02 vs 7,926.03), 0311052122, 0311050784; 11 hidden-BOE licences | +4,412,937.86 in the bulk Excel | Defect, no decision needed |
| DEF-002 | allotments 8985 ↔ BOE 26598, 9760 ↔ 3220444 and others; 8357 = duplicate of 8369 | 235,475.75 proven (+76,000 plausible) of 1,160,224.05 flagged | Decided (C-2 auto-link exact + review) |
| DEF-150 | 0910065986 allotment 10178 ↔ BOE 4849356, +7 others | 420,407.75 | Decided (C-2) |
| DEF-102 | Plan tab on 11 hidden-BOE licences | +4,412,937.86 | Decided (B) |
| DEF-003 | 5211018767, BOE 8391561 (ids 28686/27109) | 14,835.86 | Owner data check |
| DEF-004 | allotment 3743 → placeholder BOE `1234567` | 665,624.43 (net 477,524.43) | Decided DEC-03 C |
| DEF-127/128 | BOE 5128829 (43 rows qty 0); 0311010085 item 26456 | 5,056,539.16 CIF; 1,881,509.08 INR | Data review (DEC-26 C) |
| DEF-071 | 3411008583 (stored 1,639,086.95 vs live 1,895,326.95); 36 negatives stored 0.00 | Δ 256,240.00 | Defect (D-D) |

Licence-level totals (independent = engine): original CIF 2,393,537,328.28; visible BOE 1,733,748,635.75; hidden BOE
4,412,937.86; outstanding allotment 31,592,776.75; available Σ 623,782,977.92; 36 over-utilised licences Σ −7,054,283.95.

## 5. Defects

**95 defect IDs** in `SAT_DEFECT_REGISTER.md`. 94 are open: **0 Critical · 11 High · 37 Medium · 46 Low** (recounted from the register). DEF-089 was
closed as a seed artifact. The counts include data-quality and latent items, and one reclassified to a business-rule
question (DEF-100). Added in the final gap runs:
- **DEF-090** (Medium): the one-licence ledger package PDF returns HTML 500 when a supplier invoice is missing.
- **DEF-091** (Low): `reports-menu` fails in isolation, correlated with a peer's uncommitted `navConfig.ts` change.
- **DEF-092** (Low): masters real-backend specs lose the session mid-run.

High:
- Financial / export:
  - 001 AR qty
  - 002 is_boe without M2M
  - 010 false ledger FAILED
  - 070 bulk Excel without hidden-BOE deduction
- Performance: 030 BOE list N+1.
- Security:
  - 050 recover-orphan key
  - 051 viewer replaces evidence
  - 052 HTML/SVG upload → token theft → superuser
- Trade/data:
  - 123 CIF-only allocation qty double count (latent)
  - 127 BOE rows qty 0 with CIF
  - 128 CIF FC 0 with INR value

Severity changes after independent review:
- 011 High → Medium.
- 031 High → Medium.
- 037 Medium → Low.
- 053 → Low (owner attests the files hold placeholders only).
- 007 → business-rule question.

## 6. E2E, UI, API/database, export, security, performance

These are summarised in §2 and §3. Full results: `SAT_UI_UX_AUDIT.md`, `SAT_API_DATABASE_AUDIT.md`, `SAT_EXPORT_AUDIT.md` and
`SAT_SECURITY_PERFORMANCE.md`. The performance baselines and suggested regression thresholds are in
`SAT_SECURITY_PERFORMANCE.md` §Performance.

## 7. Independent reviewer findings

See `SAT_INDEPENDENT_REVIEW.md`.
- **Engine:** confirmed correct against the canonical rule on all available data.
- **Refuted headline example:** the DEF-002 pair 8357 ↔ 25789 is a duplicate allotment.
- **Statuses corrected:**
  - X03 → FAIL.
  - X07 → NOT-RUN.
  - FIN-004/005 → NOT VERIFIED ON REAL DATA.
- **Missing decision added:** DEC-41.
- **Approved decisions:** two recommendations would have reopened approved decisions, and both were corrected.
- **Not reproduced:** security items 055–065 were not reproduced by the reviewer.
- **UI/E2E review (§13):**
  - SAT-INT-004 → PASS (rule, API).
  - SAT-INT-007 → not verified on real data (DEC-41 uncovered).
  - DEF-089 closed (seed artifact).
  - Agrees with the 080–088 severities.
  - Challenged the "harness" label on the regression failures. That challenge was confirmed by the isolated reruns (DEF-091, DEF-092).

## 8. User decisions

All register questions are answered except **DEC-41** (an unlinked SALE + BOE for the same goods: double count to prevent, or a
data problem to fix by linking). Implementation of the answered decisions is gated by `SAT_IMPLEMENTATION_APPROVAL_REPORT.md`
(G1–G8). Decisions or defects added after that report was written, and to check at the gate:
- DEC-41;
- SAT-DEF-070…074 (Phase 9);
- SAT-DEF-080…089 (UI);
- the allotment `?is_approved=all` 500 (in DEF-059);
- SAT-DEF-090…092.

## 9. Remaining blockers and gaps

| Gap | Kind | What would close it |
|---|---|---|
| Trades / invoices / billed-without-BOE on real data | **Environment**: 0 trades in the local copy | Re-run the Phase 3 recompute and Phase 6 trade exports on a production-shaped copy (read-only) |
| SAT-INT-002 licence form writes, INT-009 transfer, sort / bulk / delete-confirm / dialog focus trap | Executable, NOT-RUN | Extend `frontend/e2e/sat-*.spec.ts` on the harness |
| SAT-INT-004 allotment link in the browser | PASS (rule, API). The seeded allotment is BOE-consumed and hidden by the list's default scope (Phase 9 §13) | Add a pending allotment to the seed, then drive the link in `sat-int-boe` |
| ~~X07 ledger package PDF~~ | **Done**: FAIL → SAT-DEF-090 | — |
| ~~Regression reruns~~ | **Done** in isolation: reports-menu reproducible (DEF-091); masters session loss (DEF-092) | Triage against the peer's `navConfig.ts` diff and the token-refresh flow |
| SAT-INT-010 BOE PDF upload | A path exists (Phase 9); NOT-RUN | Drive it on the harness with a synthetic PDF |
| Security 055–065 not independently reproduced; SEC-021 (no entity scoping), SEC-039/040 (pip-audit not installed, npm audit needs network) | Tooling / network | Owner provides the tools or network |
| Phase 3/6 raw logs lost (`/tmp/sat`) | Environment | Phase 9 re-derived the licence figures; the export figures rely on the report text |
| Load / soak testing, live Celery broker | Out of scope | — |

## 10. Production-readiness assessment

**Not ready for release.** Before release:
1. Fix DEF-050/051/052 (security High). These need no business decision, except the role list for 051, which is decided (DEC-35 A).
2. Fix DEF-070 and the DEF-010 presentation, and the DEF-001 item AR deduction (decided). Fix DEF-001 **before** D-D live values (DEF-072).
3. Re-verify trades and invoices on production-shaped data (they are not verified today).
4. Owner answers DEC-41 and approves the implementation gate.

The licence-level CIF balance, the core of the product, is independently verified exact and can be relied on for licences
without trades.
