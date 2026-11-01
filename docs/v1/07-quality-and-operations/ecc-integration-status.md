# ECC integration status

Status: **ACTIVE AS A SELECTIVE, PROJECT-LOCAL SKILL SET. The ECC plugin is NOT installed.** One installation method is in use: 16 ECC skills copied into `.claude/skills/`. No ECC hooks, agents, commands, MCP servers or rules are active.

Last verified: 2026-10-31 (IST), from `plugin` CLI output, on-disk inspection, and live `claude -p` runs.

## 1. Agent and integration

| Item | Verified value |
| --- | --- |
| Active coding agent in PyCharm | Claude, via `@agentclientprotocol/claude-agent-acp` **0.99.1** |
| Agent SDK used by that adapter | `@anthropic-ai/claude-agent-sdk` **0.3.312** |
| Claude Code CLI bundled with that SDK | **2.1.312** at `~/Library/Caches/JetBrains/PyCharm2026.2/acp-agents/claude-acp/0.99.1/node_modules/@anthropic-ai/claude-agent-sdk-darwin-arm64/claude` |
| `claude` on the shell `PATH` | No. The bundled binary above is used. |
| ECC minimum requirement | Claude Code 2.1 or newer. **Met.** |
| Codex CLI | `0.163.0` present. Not the workflow agent. **No Codex integration installed.** |

## 2. Why this integration

ECC's full plugin was measured as the wrong trade-off for this repository:

| Finding | Evidence |
| --- | --- |
| Full plugin adds about **48,079 tokens to every session** (ECC's own projection; not measured) | `plugin details ecc@ecc` |
| Plugin MCP servers **start automatically when the plugin is enabled** | Official docs, `code.claude.com/docs/en/mcp`: "When you enable a plugin, Claude Code starts its MCP servers automatically." The bundled `chrome-devtools` server runs `npx -y chrome-devtools-mcp@1.10.1`, an unpinned third-party package. |
| The plugin's `hooks/hooks.json` has 24 inline `node -e` commands, including `PreToolUse` gates on Bash, Edit, Write and MCP calls and 7 `Stop` hooks | Plugin cache (since removed) |
| Plugin root `CLAUDE.md` is **not** loaded as context | `plugin validate`; official manifest reference |
| ECC rules are **not** distributed by the plugin | ECC README |

Selective skills keep only the skill descriptions in context. Full skill bodies load only when invoked, per the official skills documentation.

## 3. What is installed and where

| Path | Content | Source |
| --- | --- | --- |
| `.claude/skills/<name>/SKILL.md` (16 skills, **untracked**) | `django-patterns`, `django-verification`, `django-security`, `django-tdd`, `python-testing`, `database-migrations`, `postgres-patterns`, `react-patterns`, `frontend-a11y`, `e2e-testing`, `tdd-workflow`, `security-review`, `api-design`, `search-first`, `context-budget`, `verification-loop` | ECC 2.2.3 `skills/`, copied file-for-file; SHA-256 of each copy equals its source (16/16) |
| `CLAUDE.md` (tracked) | Two-line **scope amendment** block at the top. The original "Never modify source code." rule (line 52) is unchanged. | Owner mission 2026-10-31. Review before commit. |
| `~/.claude/plugins/marketplaces/ecc/` | Marketplace clone (source for future updates and copies) | `marketplace add https://github.com/affaan-m/ECC` |
| `~/.claude/settings.json` (created) | Contains only `extraKnownMarketplaces.ecc` | Created by `marketplace add` |

Excluded on purpose: all 71 agents (they overlap names with the 17 project agents in `.claude/agents/`), all 98 command shims, all hooks, the MCP definition, and every skill outside the 16 above. The 16 were reviewed:

- Each is a single `SKILL.md`. No scripts, binaries or `hooks/` directories are present in any of them.
- A pattern scan for `curl … | sh`, `git push`, `--force`, `rm -rf`, `npm publish`, `--no-verify`, `reset --hard`, `git clean`, `chmod 777`, and `sudo` found one hit, a rule in `tdd-workflow` that **prohibits** `curl … | sh`.
- Words such as "token", "secret" and "password" appear in security examples. They are not instructions to read credentials.

## 4. Verification

| Check | Result | Evidence |
| --- | --- | --- |
| Plugin is not installed | **Verified** | `plugin list --json` → `[]`; `installed_plugins.json` → `plugins: {}` |
| Plugin cache removed | **Verified** | `~/.claude/plugins/cache/ecc` deleted after confirming no registry reference |
| SKILL.md copies match source | **Verified 16/16** | SHA-256 comparison |
| Context prefix, plugin disabled, MCP blocked, no tools | 4,904 tokens | `claude -p … --strict-mcp-config --tools ""` |
| Context prefix, final configuration, same flags | 5,186 tokens (delta 282) | Includes the CLAUDE.md amendment. `--tools ""` removes the Skill tool, so the skill listing is **not** in this figure. |
| Skill listing cost | **Not isolated.** Full-toolset runs with and without the Skill tool gave 24,649 and 22,772 tokens: the cache accounting varies too much. Estimate from description lengths: 16 descriptions, 4,383 characters, about **1,100 tokens**. | Estimate, not a measurement |
| Skills discoverable by the agent | **Verified** | Live `claude -p` run listed all six sampled skills. No user-level skill of those names exists and no plugin is installed, so they come from the project. |
| CLAUDE.md amendment in context | **Verified** | The same live run confirmed the block is present |
| ECC hooks run | **Not applicable.** No hooks installed. | Plugin removed |
| ECC MCP servers | **None.** | Plugin removed |

Rules: the CLI recognises `.claude/rules/*.md` (string search of the binary, not a live test). ECC rules are not installed.

## 5. Changed files and rollback

Backup taken **before** any change: `~/.claude/backups/ecc-install-20261031-192000/` (`chmod 700`, files `600`). Manifest `MANIFEST.txt` includes a correction: the project `.claude/settings.local.json` existed before the change and was **not** backed up byte-for-byte.

| Path | Current state | Rollback |
| --- | --- | --- |
| `~/.claude.json` | **Unchanged.** SHA-256 `c1a2a495…0a21b`, identical to backup. | None needed |
| `~/.claude/settings.json` | Created. Only `extraKnownMarketplaces.ecc`. | Delete it, as it was absent before install |
| `~/.claude/plugins/known_marketplaces.json`, `marketplaces/ecc/` | Created (marketplace registry and clone) | `claude plugin marketplace remove ecc` |
| `~/.claude/plugins/installed_plugins.json` | Created, currently empty | Ignore or delete |
| `~/.claude/plugins/cache/ecc/` | **Removed** | Reinstall if needed |
| `<repo>/.claude/settings.local.json` (git-ignored) | Permissions kept (2 entries). Temporary `enabledPlugins` key removed. Formatting may have been rewritten. | None needed for the key set |
| `<repo>/.claude/skills/` (untracked) | 16 skills | `rm -r .claude/skills` |
| `<repo>/CLAUDE.md` (tracked) | 2 inserted lines (scope amendment) | Delete the blockquote at the top, or `git checkout -- CLAUDE.md` after owner review |

Rollback order for the whole ECC integration: (1) `rm -r .claude/skills`; (2) `claude plugin marketplace remove ecc`; (3) delete `~/.claude/settings.json` if it still contains only the `ecc` entry; (4) delete the blockquote in `CLAUDE.md`.

## 6. Decisions still open

| ID | Decision | Status |
| --- | --- | --- |
| ECC-1 | Enable the full plugin | **Not recommended.** The reasons are in section 2. Enabling it would start the unpinned MCP server and the hooks. |
| ECC-2 | `chrome-devtools` MCP | **Refused by default.** Needs owner approval; cannot be disabled non-interactively. |
| ECC-3 | Context budget | Selective skills chosen (about 1,100 tokens estimated for descriptions). Full plugin (about 48k) rejected. |
| ECC-4 | Project rules location | The scope amendment lives in tracked `CLAUDE.md`. The longer rule set stays in `ecc-project-rules-draft.md` until approved. |
| ECC-5 | Tracked `CLAUDE.md` conflict | **Resolved by an explicit, reversible amendment.** Owner review required before commit. |
