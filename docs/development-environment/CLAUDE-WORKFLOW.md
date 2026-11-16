# Claude workflow

## Ground rule
Claude changes application code **only when you explicitly ask for that change**. Without such a
request it analyses, plans and reports, and never picks ERP features on its own.

## Default: fast path (most tasks)

```
SHORT PROMPT → UNDERSTAND → IMPLEMENT → TEST → REPORT
```

1. **Understand:** grep `.claude/index/`, then read only the relevant line ranges. Routine details
   come from the repo, CLAUDE.md and `.claude/memory/`; Claude doesn't re-ask what those already answer.
2. **Implement** the minimum change. Routine reversible actions run without confirmation.
3. **Test:** targeted tests first, then the area gate (`scripts/dev/quality-gate.sh backend|frontend`).
   Claude fixes the failures it introduced.
4. **Report:** short format only.

```
Status:    Completed / Blocked
Changes:   file — what changed
Tests:     Pass / Fail (NOT RUN + reason if a gate couldn't run)
Remaining: genuine outstanding items only
```
Flags are added when they apply: `BUSINESS-RULE CHANGE`, `API CONTRACT CHANGE`, `SCHEMA/MIGRATION`, `PERMISSION CHANGE`.

Claude asks a question **only** when an ambiguity materially affects architecture, data safety or behaviour.

## Substantial / multi-area tasks

```
DISCOVER → ANALYZE → PLAN → IMPLEMENT → TEST → REVIEW → VERIFY → DOCUMENT
```
Use `/orchestrate <task>`. The flow:
1. `tech-lead` plans.
2. `engineering-manager` assigns one owner per file, and parallel specialists run (worktrees if files could collide).
3. Gates run, then the independent `code-reviewer` + language reviewers + domain auditors review.
4. Findings are fixed, docs/memory updated, and you get `/report full`.
Detail: `docs/claude/ORCHESTRATION.md`.

| Situation | Approach |
|---|---|
| Small, clear change (1–3 files) | Fast path, no agents |
| Bug | Skill `debugging`; agent `debugging-specialist` only if non-trivial |
| Backend + frontend + DB | `/orchestrate`, with parallel agents only for independent parts |
| CIF / balance / BOE / allotment / invoice code | Fast or full path **plus** the matching domain auditor and a `BUSINESS-RULE CHANGE` note |
| Schema change | Skill `migration-safety`, `database-architect` design, `migrate` asks first |

## Quality is never traded for speed
Required tests run, security is reviewed for auth/API changes, existing behaviour is preserved,
DB changes are safe, no duplicate dependencies are added (`search-first`), nothing unrelated is
implemented, and failures are reported honestly.

## Token efficiency
- Index grep instead of repo scans. Never read the index tables whole.
- Skills load on demand. Agents get structured briefs and return structured summaries.
- Specialists cannot spawn agents. Haiku handles exploration.
- Checks that already passed are not re-run unless code changed.
- No long documentation for trivial changes.
- Use `/compact` (ECC `strategic-compact`) at phase boundaries in long sessions.

## Useful commands
`/quality-gate [area]` · `/review-diff` · `/cif-audit` · `/report [full]` · `/remember <fact>` · `/session-summary`
