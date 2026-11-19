#!/bin/sh
# Targeted tests for the current change, compact output, full log on disk, real exit code.
#   sh .claude/scripts/smart-test.sh                  # tests related to changed files (context-audit)
#   sh .claude/scripts/smart-test.sh backend/apps/license/tests/test_x.py frontend/src/pages/x/Y.test.tsx
# Never a substitute for the release gate: scripts/dev/quality-gate.sh.
set -u
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
LOG_DIR=${SMART_TEST_LOG_DIR:-/tmp/smart-test}
mkdir -p "$LOG_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
if [ "$#" -gt 0 ]; then TARGETS="$*"; else
  TARGETS=$(python3 "$ROOT/.claude/scripts/context-audit.py" | sed -n 's/^    tests: //p' | tr ',' '\n' | sed 's/^ *//' | grep -v '^—' | sort -u | tr '\n' ' ')
fi
PY_TESTS=$(for t in $TARGETS; do case "$t" in (backend/*.py) echo "${t#backend/}";; esac; done | sort -u | tr '\n' ' ')
FE_TESTS=$(for t in $TARGETS; do case "$t" in (frontend/*.test.ts|frontend/*.test.tsx) echo "${t#frontend/}";; esac; done | sort -u | tr '\n' ' ')
STATUS=0
if [ -n "$PY_TESTS" ]; then
  LOG="$LOG_DIR/backend-$STAMP.log"
  (cd "$ROOT/backend" && TEST_DB_NAME=${TEST_DB_NAME:-test_lmanagement_smart_$$} .venv/bin/python -m pytest --import-mode=importlib -q --no-cov -p no:cacheprovider $PY_TESTS) > "$LOG" 2>&1
  RC=$?; [ $RC -ne 0 ] && STATUS=$RC
  echo "backend exit=$RC  $(grep -E '[0-9]+ (passed|failed)' "$LOG" | tail -1)  log=$LOG"
  [ $RC -ne 0 ] && grep -E '^(FAILED|ERROR)|^E  ' "$LOG" | head -20
fi
if [ -n "$FE_TESTS" ]; then
  LOG="$LOG_DIR/frontend-$STAMP.log"
  (cd "$ROOT/frontend" && npx vitest run $FE_TESTS) > "$LOG" 2>&1
  RC=$?; [ $RC -ne 0 ] && STATUS=$RC
  echo "frontend exit=$RC  $(grep -E 'Tests +[0-9]+' "$LOG" | tail -1 | sed 's/^ *//')  log=$LOG"
  [ $RC -ne 0 ] && grep -E 'FAIL|×|AssertionError|Error:' "$LOG" | head -20
fi
[ -z "$PY_TESTS$FE_TESTS" ] && echo "No related tests found — name them explicitly or run the area gate."
exit $STATUS
