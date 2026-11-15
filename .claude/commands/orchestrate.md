---
description: Run the full multi-agent development workflow for a substantial task (plan → parallel specialists → gates → reviews → fixes → docs/memory → report)
argument-hint: <task description>
---
Task: $ARGUMENTS

Follow `docs/claude/ORCHESTRATION.md` exactly. Summary:
1. Restate requirements and acceptance criteria. If vague, consult `product-manager`; if a business rule is involved, consult `licence-domain-expert`. Ask the human only for decisions that are genuinely theirs.
2. Read `.claude/memory/README.md` and the relevant memory files. Orient via the code index (`symbols.tsv`, `dependents.tsv`) — no repo-wide scans.
3. Get a plan from `tech-lead` (plus `django-architect` / `react-architect` / `solutions-architect` if design is needed).
4. Hand the plan to `engineering-manager`: work packages with **disjoint owned files**; packages that share files or touched symbols run sequentially or with `isolation: "worktree"`.
5. Launch independent packages in parallel (one message, several Agent calls).
6. Integrate locally. Run `scripts/dev/quality-gate.sh <areas>`.
7. Parallel read-only reviews: `code-reviewer` + language reviewers; `security-auditor` if auth/API/data exposure changed; `performance-engineer` if queries/renders changed; domain auditors if `.claude/rules/business-rules.md` paths changed.
8. Fix blocking findings (max 3 rounds, then escalate). Re-run gates.
9. `technical-writer` / `architecture-documenter` update docs; append decisions to `.claude/memory/decisions.md`.
10. Final report in the `/report` format. Do not push or merge.
