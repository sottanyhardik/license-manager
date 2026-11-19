# Claude Code token optimisation — License Manager (2026-11-19)

Owner request: cut avoidable token use ≥ 50 % without losing quality, tests, security or financial integrity.
Owner answers (this session): install RTK, Context Mode, claude-mem, Context Saver (subject to vetting); continue in the
current session; ECC rules on demand; **no local models**.

## 1. Original configuration (baseline audit)

| Item | Found |
|---|---|
| Claude Code | 2.1.328 · macOS 26.6.2 arm64 · Node 24.22.3 |
| Global `~/.claude/settings.json` | JetBrains Air managed (apiKeyHelper, gateway base URL, enforced model list), 1 h prompt caching, tool search; plugin `air@air` |
| Project `.claude/settings.json` | hooks: SessionStart ×2, PreToolUse ×2 (guard_bash, pre_commit_check), PostToolUse ×2, Stop, SessionEnd; permissions 103 allow / 39 ask / 23 deny |
| Agents / skills / rules | 43 agents (16 `inherit` → ran on the parent's Opus), 32 skills, 7 project rules + **23 vendored ECC rules auto-attached by path** |
| MCP servers | none (project) |
| Memory | auto-memory (`~/.claude/projects/…/memory`), `.claude/memory/`, execution trackers — no extra memory tool needed |

## 2. Measured baseline (real API usage from transcripts — `.claude/scripts/token-report.py`)

| Session | Requests | Cache read | Cache write | Output | Recorded cost |
|---|---:|---:|---:|---:|---:|
| 7491de17 (this one, product intelligence) | 348 | 162.5 M | 0.81 M | 0.42 M | $23.81 |
| 9e29bdc4 (2026-11-18) | 511 | 249.9 M | 1.44 M | 0.48 M | $76.79 |
| 54d0f745 (2026-11-18) | 450 | 226.2 M | 1.05 M | 0.46 M | $67.29 |
| 41b3a00b (2026-11-17) | 455 | 217.8 M | 2.90 M | 0.66 M | $95.84 |

**≈ 99 % of tokens are cache reads**: the whole conversation is re-read on every request (here ≈ 467 K tokens per
request on average). The levers are therefore (1) less context injected per turn and (2) shorter, task-sized sessions —
not fewer output tokens. Largest avoidable contributors in this session: injected rule files (`nested_memory`
155 KB ≈ 39 K tokens, re-read by every later request) and Bash output (446 KB ≈ 111 K tokens).

## 3. What was installed / configured

| Change | Detail | Rollback |
|---|---|---|
| **RTK 1.2.0** (`brew install rtk`) — primary output layer | Project PreToolUse hook `rtk hook claude` (after guard + pre-commit hooks). Rewrites read-only/test/lint commands; **excluded** (never rewritten): every guarded command — git push/merge/rebase/reset/restore/checkout/cherry-pick/tag/branch/worktree/stash/clean, rm, psql, redis-cli, docker, gh, ssh/scp/rsync, pip, npm install, `manage.py migrate`, the quality-gate script. Narrow allow rules for read-only `rtk …` forms only (no blanket `Bash(rtk:*)`, which would bypass the push prompt). Telemetry off (default). Config: `~/Library/Application Support/rtk/config.toml`. | remove the hook entry + 15 `Bash(rtk …)` allows from `.claude/settings.json` (git), `brew uninstall rtk` |
| **Context Mode 2.2.1** (official marketplace) | Marketplace declared in project settings; plugin installed at **local** scope and **disabled** — it overlaps RTK on Bash output and blocks full `Read`s > 16 KB; enable only after a fresh-session A/B shows a net gain. Always-on cost ≈ 94 tokens (`claude plugin details`). | `claude plugin uninstall context-mode@context-mode --scope local`; `claude plugin marketplace remove context-mode` |
| **ECC rules on demand** | `git mv .claude/rules/ecc → .claude/reference/ecc` (23 files) + skill `ecc-guidelines` (index of when to read which file); 20 references updated. Project rules (business-rules, safety, backend, frontend, autonomous-execution, documentation-mode) stay auto-loaded. | `git mv .claude/reference/ecc .claude/rules/ecc` |
| **Token rule** `.claude/rules/token-optimization.md` (≈ 560 tokens, always on) | diff-first context loading, no re-reads, compact output, targeted tests, ≤ 3 agents, routing, planning budgets (5 K / 15 K / 30 K / 50 K), one task per session; never trade tests / reviews / CIF rules for tokens | delete file |
| **Model routing** (subagent `model:` frontmatter — the supported mechanism) | Opus: all financial/domain auditors (cif-balance, boe-reconciliation, dgft-dfia, **invoice-auditor** was Sonnet), security-auditor, architects, tech-lead, solutions-architect, licence-domain-expert, engineering-manager · Sonnet: implementation, reviewers, QA, data, devops, product/UX (16 agents moved off `inherit`) · Haiku: technical-writer, architecture-documenter, code-explorer. No local models. | `git checkout -- .claude/agents` *(asks first)* or revert the frontmatter lines |
| **Scripts** `.claude/scripts/` | `token-report.py` (measured usage per session), `context-audit.py` (changed files → blast radius from `.claude/index/` → related tests → business-rule / migration flags → decisions), `smart-test.sh` (targeted pytest/vitest with own `TEST_DB_NAME`, compact result, log on disk, real exit code) | delete |

Backups of both settings files before any change: `~/lm_backups/claude-config-2026-11-19/`.

## 4. Not installed, and why

| Tool | Reason |
|---|---|
| **claude-mem** | Runs a background "observer" agent that makes **extra model calls** (default provider is its own service — free trial, then a payment method; otherwise your plan or an OpenRouter/Gemini key), telemetry **on** by default, magic-link sign-in; with the default provider ERP tool activity would leave the machine. Adds tokens rather than saving them and duplicates the existing memory/tracker system. Its README asks agents not to make these setup choices for you → **owner decision needed** (provider, telemetry off, sign-in) before installing. |
| **Context Saver** | 0 stars / 5 commits / no releases (unvetted code running on every Bash call); replaces large output with **Sonnet summaries via `claude -p`** (~$0.04 each) — summaries can hide test-failure detail (violates "never hide failures") and overlaps RTK / Context Mode. Not installed; owner may override knowingly. |
| More ECC components | ECC agents/skills/rules are already vendored and curated; installing the full set would duplicate them. |

## 5. Measured reductions (bytes of context, ≈ bytes / 4 tokens — not API-token measurements)

**Rule injection per file touch** (rules matched by path; before = with ECC auto-load):

| First touch of… | Before | After | Saved |
|---|---:|---:|---:|
| backend `.py` | 25,260 B | 11,106 B | 56 % |
| frontend `.tsx` | 56,897 B | 8,595 B | 85 % |
| frontend `.test.tsx` | 63,924 B | 8,595 B | 87 % |
| `.css` | 32,566 B | 8,595 B | 74 % |
| `docs/*.md` | 9,528 B | 9,528 B | 0 % |
| **All five** | **188,175 B** | **46,419 B** | **75 % (~35 K tokens)** |

Each injected token is re-read by every later request, so a session touching backend + frontend files avoids
≈ 35 K tokens × remaining requests of cache reads.

**RTK on real commands in this repo** (raw → RTK): pytest passing suite 564 → 28 B (−95 %), `ls -la` 7,161 → 1,773 B
(−75 %), `git log -30` 31,656 → 10,664 B (−66 %), `grep -rn` 907 → 699 B (−23 %), `git status` 6,977 → 6,037 B (−14 %),
`git diff --stat` unchanged. A failing pytest kept the full assertion detail and exit code 1 (verified).

## 6. What is NOT yet measured (honest status)

- **The ≥ 50 % target is not demonstrated.** Real API-token A/B needs equivalent tasks in fresh sessions before and
  after (this session's own context distorts any in-session measurement). Method: run the same small task (e.g. a
  scoped bug fix + targeted tests) in a new session, then `python3 .claude/scripts/token-report.py --session <id>` and
  compare requests × cache-read against the baseline rows above.
- Expected from the measured parts: rule trimming ≈ 35 K tokens less context per mixed session (≈ 5–10 % of a typical
  session's cache reads); RTK 50–95 % less command output on test/log/listing commands. The single largest lever is
  behavioural — **task-sized sessions**: this session averaged ≈ 467 K tokens of context per request; sessions kept to one
  workstream (handoff via `/session-summary`) would cut cache reads several-fold. That is a recommendation, not a
  measurement.
- Context Mode: no offline benchmark ships in the plugin package (`bench/` is absent); left disabled.

## 7. How to use

```bash
python3 .claude/scripts/context-audit.py            # what to read / which tests for the current diff
sh .claude/scripts/smart-test.sh                     # targeted tests for the diff (or pass test paths)
python3 .claude/scripts/token-report.py --session <id>   # measured usage + biggest tool outputs + injected context
rtk gain                                             # RTK's own (byte-estimated) savings
rtk recall <id>                                      # full original output of a compacted command
```

## 8. Rollback (all reversible)

1. `.claude/settings.json`: remove the `rtk hook claude` entry and the `Bash(rtk …)` allows (or restore the backup).
2. `brew uninstall rtk`; delete `~/Library/Application Support/rtk/`.
3. Context Mode: `claude plugin uninstall context-mode@context-mode --scope local`; `claude plugin marketplace remove context-mode`.
4. ECC: `git mv .claude/reference/ecc .claude/rules/ecc`; remove `.claude/skills/ecc-guidelines/`; revert the path text.
5. Routing: revert the `model:` lines in `.claude/agents/*.md` (git diff shows exactly 19 lines).
6. Delete `.claude/rules/token-optimization.md` and `.claude/scripts/{token-report.py,context-audit.py,smart-test.sh}`.
