#!/bin/bash
#
# scripts/development/check-dev-ports.sh — read-only check of the local dev stack.
#
# Reports every listener on the backend (8000) and frontend (5173) ports and exits
# non-zero when the browser could reach more than one backend, or a stale
# `--noreload` launch agent is loaded. It never stops a process.
#
# Why this exists: a `--noreload` backend left running serves old code while the
# browser keeps talking to it, so the dashboard shows contract errors that look
# like a code bug. Run this before debugging a dashboard response.
#
set -uo pipefail

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
AGENT_LABEL="com.license-manager.backend"
status=0

describe() {
    local pid="$1"
    local command started
    command="$(ps -o command= -p "$pid" 2>/dev/null | cut -c1-160)"
    started="$(ps -o lstart= -p "$pid" 2>/dev/null)"
    echo "    pid $pid  started $started"
    echo "    $command"
}

check_port() {
    local port="$1" label="$2" pids
    pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | sort -u)"
    if [[ -z "$pids" ]]; then
        echo "$label :$port  no listener"
        return
    fi
    local count
    count="$(echo "$pids" | wc -l | tr -d ' ')"
    echo "$label :$port  $count listener(s)"
    for pid in $pids; do describe "$pid"; done
    if [[ "$label" == "backend" && "$count" -gt 1 ]]; then
        echo "  FAIL: more than one backend listener. The browser may reach a stale one."
        status=1
    fi
}

check_port "$BACKEND_PORT" backend
check_port "$FRONTEND_PORT" frontend

if launchctl print "gui/$(id -u)/$AGENT_LABEL" >/dev/null 2>&1; then
    echo "launch agent $AGENT_LABEL  loaded"
    echo "  WARN: serve-backend.sh runs --noreload and is not restarted on code changes."
    echo "        Unload it with: launchctl bootout gui/\$(id -u)/$AGENT_LABEL"
    status=1
else
    echo "launch agent $AGENT_LABEL  not loaded"
fi

exit "$status"
