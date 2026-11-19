# Token discipline (always applies; owner 2026-11-19) — optimise context, never engineering quality

Measured: cost is dominated by the context re-read on every request (≈99 % cache reads). Keep the context small.
- **Diff first, then only what it touches:** `git diff --stat` → `.claude/scripts/context-audit.py` (changed files,
  dependents from `.claude/index/`, related tests, decisions) → read only those line ranges. Never scan the repo.
- **Do not re-read** an unchanged file already in context; use `Read` with `offset`/`limit` for large files.
- **Compact output:** RTK rewrites git / test / lint / ls / grep commands (errors + exit codes kept; full output via
  `rtk recall`). Never pipe huge logs into context — write to `/tmp/…` and grep the failing lines.
- **Tests:** `.claude/scripts/smart-test.sh` for targeted runs (own `TEST_DB_NAME`, log on disk, exit code); full
  gates once per integration (`scripts/dev/quality-gate.sh`). Targeted runs never replace the release gate.
- **Agents:** ≤ 3 by default, narrow brief (files, output, acceptance, stop condition); never two agents on the
  same files; reuse findings instead of re-reviewing unchanged code.
- **Model routing (subagent `model:` only — verified via the agent frontmatter):** haiku = lookups, docs, log
  summaries; sonnet = implementation, normal reviews; opus = architecture, financial / CIF / BOE / allotment /
  migration / security final review. Never downgrade those critical reviews. No local models (owner decision).
- **Planning budgets (not hard limits — never abandon required work):** simple ≈ 5 K, feature ≈ 15 K, complex ≈ 30 K,
  critical architecture ≈ 50 K tokens of exploration. Near the budget: stop exploring, summarise findings with file:line
  references, list open work, continue with only the relevant context.
- **Sessions:** one task per session; write a handoff (`/session-summary`) and start fresh instead of growing a
  session past one workstream. Never clear a session with unfinished work.
- **Never** trade away tests, reviews, migrations checks, security, or the canonical CIF rules (`business-rules.md`)
  for tokens, and never rely on compressed summaries for financial changes — read the exact source.
