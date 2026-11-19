# ECC + Claude Code setup — License Manager

Last verified: 2026-11-16 on macOS 26.6.2 (Apple Silicon), branch `feature/v5`.

## Toolchain (inspected)

| Item | Value |
|---|---|
| Claude Code | 2.1.325 at `~/.local/bin/claude` (on `PATH` via `~/.zshrc`) |
| Node / npm | v24.22.3 / 11.19.1 |
| Python | 3.14.10 |
| git / gh | 2.56.1 / 2.104.0 |
| IDE | PyCharm (`/Applications/PyCharm.app`), `.idea/` present, JetBrains plugin `jetbrains-central` (user scope) |
| MCP | `pycharm` (HTTP, provided by the IDE) — connected |

## ECC installation model

**Everything Claude Code (ECC), v2.2.3 — commit `d2ef2680…`, MIT** — is installed as a **curated,
vendored subset** inside `.claude/` (record: `.claude/ECC_VENDORED.txt`, licence: `.claude/ECC_LICENSE`).
On 2026-11-16 `git ls-remote https://github.com/affaan-m/ECC` confirmed upstream `HEAD` = `d2ef268`
and the newest tag = `v2.2.3`, so the vendored copy **is the latest stable release**. No reinstall was needed.

Why vendored instead of the full plugin (decision 2026-11-15, `.claude/memory/decisions.md`):
- The full ECC plugin adds well over 100 agents/skills/commands. Every description goes into context
  each session, which costs tokens and makes routing noisy.
- Several ECC agents duplicate project agents that carry domain knowledge (`code-reviewer`,
  `security-reviewer`, `architect`, …).
- ECC's global hooks and fixed 80%-coverage / git-workflow rules conflict with this repo's policy.

| ECC capability | Where it lives here |
|---|---|
| Specialist agents | 12 ECC agents in `.claude/agents/` (origin E in the roster), each with a project-context section |
| Skills | 18 ECC skills in `.claude/skills/` (`metadata.origin: ECC`) |
| Rules | `.claude/reference/ecc/{common,python,typescript,react,web}` (lower precedence than project rules) |
| Hooks | Project-native hooks (`.claude/hooks/`) instead of ECC's Node hooks (`ECC_HOOK_PROFILE=minimal` kept for the opt-in plugin) |
| Commands / workflows | Project commands `/orchestrate /quality-gate /review-diff /cif-audit /report /remember /session-summary` |
| Memory / context | `.claude/memory/` (shared) + `.claude/index/` (auto-rebuilt code index) + ECC `strategic-compact`, `context-budget` |
| Planning / TDD / review / verification / security | see `SKILL-CATALOG.md` |

**Optional full plugin (not installed):** `bash scripts/dev/bootstrap-macos.sh --with-ecc-plugin`, or
inside Claude: `/plugin marketplace add affaan-m/everything-claude-code`, then `/plugin install`.
If you install it, use project scope, keep `ECC_HOOK_PROFILE=minimal`, and expect duplicate agent names.

## Configuration layers

| Layer | File | Notes |
|---|---|---|
| Global (user) | `~/.claude/settings.json` | Managed by JetBrains Air (API proxy, model picker). **Left untouched** on purpose. |
| Project (shared, committed) | `.claude/settings.json` | Permissions, hooks, env — see `HOOKS-AND-PERMISSIONS.md` |
| Project (personal, git-ignored) | `.claude/settings.local.json` | One-off allows; left as is |
| Instructions | `CLAUDE.md` + `.claude/rules/*.md` (path-scoped) | Loaded natively at session start |
| Agents / skills / commands | `.claude/agents/`, `.claude/skills/`, `.claude/commands/` | Auto-discovered |

## PyCharm terminal workflow

1. Open the repo in PyCharm, then open the terminal (⌥F12). zsh loads `~/.zshrc`, so `claude` is on `PATH`.
2. Run `claude` from the repo root. The IDE MCP (`pycharm`) connects automatically through the JetBrains plugin.
   Check with `claude mcp list`.
3. Read-only PyCharm MCP tools (symbol search, problems, lint, git status) are pre-allowed. SQL execution,
   data import and run configurations prompt every time.

## Maintenance

- Update ECC: compare `git ls-remote https://github.com/affaan-m/ECC HEAD` with `.claude/ECC_VENDORED.txt`.
  Re-vendor only the files listed in the roster, and keep the appended project-context sections.
- Hook self-tests: `python3 .claude/hooks/test_guard_bash.py && python3 .claude/hooks/test_hooks.py`.
- Environment doctor: `sh scripts/dev/doctor.sh`.
