#!/bin/sh
# SessionStart hook: inject a 2-line orientation into context. CLAUDE.md itself is loaded
# natively by Claude Code — this only adds live git state + the scope rule. Read-only, < 100 ms.
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$ROOT" ] && exit 0
cd "$ROOT" || exit 0
BR=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
DIRTY=$(git status --porcelain 2>/dev/null | grep -v '\.DS_Store$' | wc -l | tr -d ' ')
echo "[license-manager] branch=$BR, $DIRTY uncommitted file(s) besides .DS_Store (treat as user work: never discard or overwrite)."
echo "[license-manager] Scope rule: change application code ONLY when the user explicitly requests it; otherwise analyse/plan/report. Workflow: docs/development-environment/CLAUDE-WORKFLOW.md"
# Autonomous execution: resume from the persistent tracker's verified checkpoints
# (rules: .claude/rules/autonomous-execution.md). Prints each CHECKPOINT:<name> block, capped.
TRACKER="docs/ERP_AUTONOMOUS_EXECUTION_STATUS.md"
if [ -f "$TRACKER" ]; then
  echo "[license-manager] Autonomous workflow: read $TRACKER and continue from the last verified checkpoint; wait for running gates/agents, never duplicate them; full gates once per integration (.claude/rules/autonomous-execution.md)."
  awk '/<!-- CHECKPOINT:[a-z0-9_-]+:BEGIN -->/{p=1;next} /<!-- CHECKPOINT:[a-z0-9_-]+:END -->/{p=0;next} p' "$TRACKER" | head -n 30
fi
exit 0
