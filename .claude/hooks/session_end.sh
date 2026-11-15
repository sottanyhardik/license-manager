#!/bin/sh
# SessionEnd hook: append a one-line, zero-token session summary to project memory.
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0
BR=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
HEAD=$(git log -1 --format=%h 2>/dev/null)
DIRTY=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
FILES=$(git status --porcelain 2>/dev/null | awk '{print $2}' | grep -v '^\.idea/' | head -8 | tr '\n' ' ')
mkdir -p .claude/memory
printf '%s | branch=%s head=%s | %s uncommitted | %s\n' "$(date '+%Y-%m-%d %H:%M')" "$BR" "$HEAD" "$DIRTY" "$FILES" >> .claude/memory/session-log.md
# keep last 200 lines
tail -n 200 .claude/memory/session-log.md > .claude/memory/.session-log.tmp && mv .claude/memory/.session-log.tmp .claude/memory/session-log.md
exit 0
