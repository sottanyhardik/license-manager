---
name: license-manager-domain
description: License Manager domain orientation — DGFT DFIA/Advance licences, SION norms, import/export items, allotments, bills of entry (BOE), trades/invoices, CIF balances — and where each concept lives in code. Use before designing or implementing any ERP task that touches licence, allotment, BOE, trade or SION logic.
metadata:
  origin: project
---

# license-manager-domain

1. **Purpose** — give agents correct domain vocabulary and code locations without re-scanning the repo.
2. **Invocation criteria** — any task touching `backend/apps/{license,allotment,bill_of_entry,trade,reconciliation}`,
   SION/norm planning, or financial screens; or when a request uses domain terms you can't map to code.
3. **Required context** — `.claude/memory/domain.md` (facts + code pointers), `.claude/rules/business-rules.md`,
   `.claude/state/decisions-snapshot.md`, `docs/06-business-rules.md` (if present), agent `licence-domain-expert`.
4. **Workflow** — (a) read `memory/domain.md`; (b) map each term to a symbol via
   `grep -i "<term>" .claude/index/symbols.tsv`; (c) confirm semantics with the approved decision rows;
   (d) if still ambiguous, ask `licence-domain-expert` (read-only) and, failing that, the owner.
5. **Restrictions** — never infer a business rule from code behaviour alone (code may be the bug —
   see ED-000); never resolve OD-11…OD-20; DGFT policy claims need a source (doc or owner).
6. **Acceptance criteria** — the task brief names each domain concept with its code location and the
   governing rule/decision, or explicitly flags it as unresolved.
7. **Verification commands** — `grep -i "<symbol>" .claude/index/symbols.tsv`;
   `shasum -a 256 docs/erp-transformation/12-decisions-register.md` vs the snapshot header.
8. **Documentation references** — `.claude/memory/domain.md`, `.claude/rules/business-rules.md`,
   `docs/erp-transformation/`, `.claude/agents/licence-domain-expert.md`, `dgft-dfia-rules-auditor.md`.
