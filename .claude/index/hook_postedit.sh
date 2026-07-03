#!/bin/sh
# PostToolUse hook: re-index the single file Claude just edited (instant, silent).
# Reads the tool-call JSON on stdin, extracts tool_input.file_path.
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
FILE=$(python3 -c 'import sys,json
try:
    d=json.load(sys.stdin)
    print((d.get("tool_input") or {}).get("file_path",""))
except Exception:
    print("")' 2>/dev/null)
[ -z "$FILE" ] && exit 0
python3 "$ROOT/.claude/index/build_index.py" --file "$FILE" >>"$ROOT/.claude/index/index.log" 2>&1 || true
exit 0
