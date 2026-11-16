---
name: financial-ledger
description: Guard rails for any change to CIF/balance math, the financial ledger, running balances, allotment/BOE/invoice reconciliation or their API/PDF/Excel outputs in the License Manager. Use whenever a task touches balance_calculator, ledger builders, canonical ledger service, materialized views, trade running balance or balance UI.
metadata:
  origin: project
---

# financial-ledger

1. **Purpose** — keep financial figures correct and consistent across engine, API, screen, PDF and Excel.
2. **Invocation criteria** — any path listed in `.claude/rules/business-rules.md`; any field named
   `*_cif`, `*balance*`, `is_over_utilised`, `trade_running_balance`; ledger exports.
3. **Required context** — `.claude/rules/business-rules.md` (canonical rule + code map);
   approved decisions OD-01, OD-02, OD-03, OD-10, OD-21 (register rows, not just the snapshot);
   open OD-11 (invoice rounding), OD-12 (outstanding allotment), OD-13 (item qty), OD-14 (commission),
   OD-15 (rounding/tolerances) — **do not decide these**.
4. **Workflow** — (a) characterization test pinning current figures on a fixture (`regression-first`);
   (b) state the governing decision for every number you change; (c) Decimal end-to-end, explicit
   quantize at the documented boundary only; (d) negative Available CIF preserved and flagged (OD-01);
   (e) authoritative Available CIF = `calculate_financial_balance` (OD-02/OD-10); customs figure only as
   `customs_available_cif`; (f) one licence-wide running balance, COMMISSION excluded but visible (OD-03);
   (g) same canonical dataset for screen/API/PDF/Excel — add a parity test; (h) `cif-balance-auditor` review.
5. **Restrictions** — no floor-at-0/clamps in authoritative calcs; no float; no silent API shape change;
   no new rounding modes; no double counting across allotment/BOE/invoice; final report must contain
   "BUSINESS-RULE CHANGE" if any figure changes.
6. **Acceptance criteria** — before/after figures explained by an approved decision; parity test passes;
   `cif-balance-auditor` verdict recorded in the queue.
7. **Verification commands** — `cd backend && TEST_DB_NAME=<db> python -m pytest apps/license -k balance -q`;
   `/cif-audit`; `sh scripts/dev/quality-gate.sh backend`.
8. **Documentation references** — `.claude/rules/business-rules.md`, `.claude/commands/cif-audit.md`,
   `.claude/agents/cif-balance-auditor.md`, `docs/erp-transformation/12-decisions-register.md`.
