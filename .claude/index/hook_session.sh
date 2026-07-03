#!/bin/sh
# SessionStart hook: reconcile the whole tree against the manifest so edits made
# outside Claude (PyCharm, git pull, etc.) are picked up. Incremental via sha,
# so this is ~0.25s on a clean tree.
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
python3 "$ROOT/.claude/index/build_index.py" >>"$ROOT/.claude/index/index.log" 2>&1 || true
exit 0
