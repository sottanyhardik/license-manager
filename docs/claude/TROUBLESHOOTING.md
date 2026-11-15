# Troubleshooting — Claude dev environment

| Symptom | Cause / fix |
|---|---|
| `zsh: command not found: claude` | `~/.local/bin` is missing from PATH. `source ~/.zshrc` (the line was added on 2026-11-15) or open a new terminal |
| PyCharm plugin can't find Claude | Settings → Tools → Claude Code → command = `/Users/<you>/.local/bin/claude` |
| Claude doesn't see the current file/selection | Start `claude` from PyCharm's terminal, run `/ide`, check the plugin is enabled |
| `BLOCKED by .claude/hooks/guard_bash.py: …` | You hit the safety boundary on purpose (push/force/deploy/remote DB/secret read). Run the command yourself, or approve it explicitly in chat. For a false positive, fix the regex in `guard_bash.py` and test with `echo '{"tool_input":{"command":"…"}}' \| python3 .claude/hooks/guard_bash.py; echo $?` |
| Quality gate shows `NOT RUN … Python >= 3.14` | Run `bootstrap-macos.sh`, or `PYTHON=/path/to/python3.14 sh scripts/dev/quality-gate.sh backend` |
| `NOT RUN … Postgres not reachable` | `sh scripts/dev/services.sh start` |
| `NOT RUN … npm not installed` | `brew install node@24` (bootstrap step 3) |
| Index seems stale | `python3 .claude/index/build_index.py`; the log is in `.claude/index/index.log` |
| Hook errors mentioning `node` | The ECC plugin's hooks were enabled without Node. Install Node or `/plugin disable ecc@ecc` |
| Duplicate hook execution | ECC hooks copied into `settings.json` **and** the plugin installed. Remove one |
| Agent not listed in `/agents` | Frontmatter must start at line 1 with `---` and have `name:` + `description:`. `sh scripts/dev/doctor.sh` checks this |
| Too many permission prompts | Add read-only commands to `.claude/settings.local.json` (git-ignored) `permissions.allow`, or use `/fewer-permission-prompts` |
| Need the old config back | Everything is in `.claude/backups/2026-11-15-pre-ecc/` |
