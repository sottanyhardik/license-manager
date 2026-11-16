# Decisions snapshot — READ-ONLY

> **Do not edit.** This is a point-in-time copy for agents' quick orientation.
> **Canonical source:** `docs/erp-transformation/12-decisions-register.md` (owner decisions) and
> `.claude/memory/decisions.md` (one-line mirror). If this snapshot and the register disagree, the
> **register wins** and the snapshot is stale — tell the orchestrator; never "fix" the decision.
>
> Snapshot taken: 2026-11-16 · register sha256 at snapshot:
> `8966eb48b3e302d90519f16010e5d8d15be3d6cccb09ecc0290d3734b8f4f926`
> (register is an *uncommitted* working-tree edit on `feature/version5` at that time).
> Staleness check: `shasum -a 256 docs/erp-transformation/12-decisions-register.md`

## Rules for every agent

1. Approved decisions (below) are binding. Implement them exactly as worded in the register; read the
   register row, not just this summary, before touching related code.
2. **Unresolved decisions OD-11 … OD-20 are OPEN.** No agent may choose an outcome, implement a
   "recommended" option, or write code/tests that presuppose one. Work that depends on an open
   decision → task state `blocked`, note `blocked-on: OD-NN`, escalate to the owner.
3. No agent may invent financial business rules (CIF, balances, rounding, allocation, commission,
   tolerances). Canonical rule text: `.claude/rules/business-rules.md`.
4. Any change touching balance/CIF math → `cif-balance-auditor` review + "BUSINESS-RULE CHANGE" note.

## Approved owner decisions (binding)

| ID | Approved (summary — read the register row) | Status at snapshot |
|---|---|---|
| OD-01 | Show actual negative Available CIF; `is_over_utilised` flag; no floor-at-0 in authoritative financial calcs or downstream re-clamps | Done `1437b381`; follow-ups OD-01b (customs/item floors), OD-01c (plan status) |
| OD-02 | `calculate_financial_balance` = authoritative Available CIF; customs figure exposed separately as `customs_available_cif` | Partial — `customs_available_cif` field + label pending |
| OD-03 | One licence-wide running balance; COMMISSION excluded but visible; same canonical dataset for screen/API/PDF/Excel; no per-company authoritative balances | Verify |
| OD-04 | Single-tenant; no Organization/tenant scoping; enforce existing RBAC consistently | Recorded (no build) |
| OD-05 | Keep MDS as an independent service/API boundary; document contracts/ownership/sync; keep clients compatible | Pending |
| OD-06 | Amended security package APPROVED 2026-11-16: repo-side + local only; hard-cut SECRET_KEY rotation; targeted .gitignore; config guard; reset/cleanup commands built **not executed**; history preserved; PDFs kept. Production rotation, history rewrite, push, deploy, running cleanup = separate approvals | Uncommitted work in parent tree — **do not alter** |
| OD-07 | Additive `/api/v1/` aliases + OpenAPI; refresh JWT → Secure HttpOnly cookie behind a feature flag with CSRF/SameSite; no breaking cutover | Pending |
| OD-08 | Remove verified §A dead code in one batch (after re-verification + manifest); archive §B root reports; review §C scripts individually | Manifest ready; batch removal next |
| OD-09 | Reuse existing form libs only (no RHF/Zod without new decision); adopt drf-spectacular; adopt pip-audit in CI | Done `6f586184` |
| OD-10 | Financial Ledger Current Balance = `calculate_financial_balance`; trade-only total = labelled `trade_running_balance` | Done `ea029f1d` + `1437b381` |
| OD-21 | Item pivot: planned and unplanned rows separate; planned totals only planned rows; no merging of descriptions/HSNs from unplanned rows | Done `91407568`; UNPLANNED label follow-up |

## OPEN — owner decision required (agents must not decide)

| ID | Question (summary) |
|---|---|
| OD-11 | Invoice PDF total + round-off: print stored `total_amount`? one rounding mode? |
| OD-12 | Outstanding allotment definition (AR vs AT); partial-allocation netting |
| OD-13 | Item available qty: live Decimal vs stored float-truncated; exclude hidden BOEs? |
| OD-14 | Commission trades in balance — symmetric or excluded |
| OD-15 | Trade line rounding, Null-DFIA threshold, profit definition, tolerances |
| OD-16 | `on_delete=PROTECT` for financial FKs |
| OD-17 | Sanitised production snapshot for trade/allocation testing |
| OD-18 | Activity-log retention window/archive |
| OD-19 | Retire 3 unused materialized views; status of `ebrc_*`/`eScrap_*` tables |
| OD-20 | BOE natural key; credit rows with NULL BOE business key |

Engineering decisions ED-000…ED-007, ED-A01 (modular monolith, no new services) are in register §A.
