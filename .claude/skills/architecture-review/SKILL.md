---
name: architecture-review
description: Review a proposed design or diff for module boundaries, coupling, contracts and long-term fit. Use before structural changes or new modules.
metadata:
  origin: project
---
1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges.
2. Compare against `docs/02-architecture.md` and decisions in `docs/decisions/`.
3. Check: app boundaries (`accounts, license, allotment, bill_of_entry, trade, reconciliation, core, tasks`), service-layer use (`apps/*/services/`), API contract stability, migration impact, frontend shared primitives (`components/ui`, axios, contexts).
4. Escalate any business-rule/contract change to the human.
5. Delegate depth only when needed: `solutions-architect` (system), `django-architect` / `react-architect` / `database-architect`.

**Output:** Verdict (approve / approve-with-changes / reject) · risks · required changes · "ADR needed: yes/no" (ADRs go in `docs/decisions/`).
