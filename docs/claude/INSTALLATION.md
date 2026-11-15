# Installation — Claude Code + ECC + JetBrains dev machine (macOS, Apple Silicon)

## State found on 2026-11-15

| Component | Status |
|---|---|
| Claude Code CLI | installed, 2.1.325 (`~/.local/bin/claude`). That directory was missing from PATH; it's now added to `~/.zshrc` |
| PyCharm 2026.3 | installed; the PyCharm MCP server is already connected to Claude (`mcp__pycharm__*` tools) |
| Claude Code JetBrains plugin | **not installed** |
| Homebrew, Node/npm, gh, uv | **not installed** |
| Python | system 3.9.6; repo `.venv` is 3.9. CI requires **3.14** and Django 6 |
| Postgres 16 / Redis | **not installed** (backend tests need both, as in CI) |

## 1. Run the bootstrap (once, in Terminal.app, not inside Claude)

```bash
cd ~/PycharmProjects/license-manager
bash scripts/dev/bootstrap-macos.sh            # add --with-ecc-plugin for the full ECC plugin
```

It installs Homebrew (asks for your password), node@24, gh, uv, postgresql@18, redis, ripgrep and jq.
It also creates `.venv-3.14` with backend/MDS test deps, runs `npm ci`, and creates the local
`lmanagement` and `master_data` databases (same credentials as CI, local only). Finally it installs
the PyCharm Claude Code plugin if PyCharm is closed.

Then: `gh auth login` (GitHub CLI) and open a new terminal.

## 2. JetBrains integration

1. PyCharm → Settings → Plugins → Marketplace → **Claude Code** → Install → restart.
2. Settings → Tools → **Claude Code**: Claude command = `~/.local/bin/claude`.
3. Settings → Python Interpreter → add existing `.venv-3.14/bin/python`.
4. Settings → Tools → **MCP Server** → keep enabled. This gives Claude file problems/diagnostics, symbol
   search, run configurations, VCS status and DB tools. It's already active in this setup.
5. Start Claude in PyCharm's terminal (`claude` or ⌘⎋). The plugin gives Claude:
   - the current file and selection (⌥⌘K inserts a file reference)
   - diffs shown in the IDE diff viewer
   - IDE diagnostics (lint/type errors)
   Run `/ide` inside Claude if it doesn't connect automatically.
6. Several agents at once: open several terminal tabs, each running `claude`. For parallel feature work, use
   `claude --worktree` or have agents use `isolation: "worktree"` (see ORCHESTRATION.md).

## 3. ECC

- **Default (installed):** curated ECC v2.2.3 subset vendored into this repo. Provenance:
  `.claude/ECC_VENDORED.txt`; license: `.claude/ECC_LICENSE` (MIT). It contains:
  - 12 agents in `.claude/agents/`
  - 18 skills in `.claude/skills/`
  - Python/React/TypeScript/web/common rules in `.claude/rules/ecc/`, path-scoped
- **Optional full plugin:** `bootstrap-macos.sh --with-ecc-plugin`, or inside Claude run
  `/plugin marketplace add https://github.com/affaan-m/ECC` and then `/plugin install ecc@ecc`.
  This needs Node. `.claude/settings.json` sets `ECC_HOOK_PROFILE=minimal`. Don't copy ECC hooks into
  `settings.json` as well, because the plugin auto-loads them and copies would run twice.

## 4. Verify

```bash
sh scripts/dev/doctor.sh              # environment health (read-only)
sh scripts/dev/quality-gate.sh all    # CI-equivalent gates; exit 0 pass / 1 fail / 3 not-run
claude                                 # then: /agents  (should list ~40 project agents), /orchestrate …
```

## What Claude can and cannot do on this machine

Claude configures the repo and can run local commands. It can't install Homebrew (that needs your
password), and piping remote install scripts into a shell is blocked by policy. That's why system installs
go through `bootstrap-macos.sh`, which you run yourself.
