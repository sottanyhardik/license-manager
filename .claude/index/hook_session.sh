#!/bin/sh
# SessionStart hook: reconcile the whole tree against the manifest so edits made
# outside Claude (PyCharm, git pull, etc.) are picked up. This re-reads changed
# source and refreshes the on-disk index (symbols.tsv / dependents.tsv /
# CODE_MAP.md / manifest.json). Incremental via sha, so ~0.25s on a clean tree.
#
# IMPORTANT: output goes to the log, NOT to the chat — the index is rebuilt at
# zero chat-token cost. The model consults it on demand via grep (see CLAUDE.md);
# it is intentionally NOT dumped into context, which would cost ~7k tokens/session.
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
python3 "$ROOT/.claude/index/build_index.py" >>"$ROOT/.claude/index/index.log" 2>&1 || true
exit 0
