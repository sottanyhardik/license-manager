#!/usr/bin/env bash
#
# deploy-mds.sh — idempotent in-place deploy of the Master-Data Service (ADR-001).
#
# Runs ON the MDS host, from the master-data-service checkout, as the service
# user (or via sudo -u mds). It does NOT ssh anywhere and does NOT touch any
# consumer/source database — it only builds and (re)starts this service.
#
# Steps: pip install -r requirements-prod.txt -> migrate -> collectstatic ->
#        systemctl restart mds -> curl /healthz.
#
# SAFETY: DRY-RUN by default. It PRINTS every state-changing command and does
# nothing until you pass --confirm. Secrets are read from the environment /
# EnvironmentFile; none are printed.
#
# Usage:
#   bash deploy/deploy-mds.sh                 # dry-run: show the plan
#   bash deploy/deploy-mds.sh --confirm       # actually deploy
#
# Env overrides:
#   MDS_DIR        checkout dir            (default: parent of this script)
#   MDS_VENV       virtualenv dir          (default: $MDS_DIR/.venv)
#   MDS_SERVICE    systemd unit name       (default: mds)
#   MDS_HEALTH_URL health probe URL        (default: http://127.0.0.1:8100/healthz)
#   MDS_PY_REQ     requirements file       (default: requirements-prod.txt)
#
set -euo pipefail

# --- Resolve paths ----------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MDS_DIR="${MDS_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
MDS_VENV="${MDS_VENV:-$MDS_DIR/.venv}"
MDS_SERVICE="${MDS_SERVICE:-mds}"
MDS_HEALTH_URL="${MDS_HEALTH_URL:-http://127.0.0.1:8100/healthz}"
MDS_PY_REQ="${MDS_PY_REQ:-requirements-prod.txt}"
PY="$MDS_VENV/bin/python"
PIP="$MDS_VENV/bin/pip"

CONFIRM=0
for arg in "$@"; do
    case "$arg" in
        --confirm) CONFIRM=1 ;;
        -h|--help)
            grep '^#' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "ERROR: unknown argument: $arg" >&2; exit 2 ;;
    esac
done

log()  { printf '=== %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

print_rollback() {
    cat <<'ROLLBACK_TEXT'
--- ROLLBACK ---
  1. Revert code:   cd <checkout> && git checkout <previous-good-sha> && bash deploy/deploy-mds.sh --confirm
  2. If a migration is the problem, roll it back explicitly BEFORE restarting:
        .venv/bin/python manage.py migrate masters <previous_migration_number>
     (only if the migration is reversible; take a pg_dump of the MDS DB first).
  3. Restart:       sudo systemctl restart mds && systemctl status mds
  4. Verify:        curl -fsS http://127.0.0.1:8100/healthz
  The service DB is MDS-only; consumers read their local mirror and are
  unaffected by an MDS restart (reads never touch MDS — ADR Decision 3).
ROLLBACK_TEXT
}

# run "<description>" cmd args...
# Dry-run: prints the command. --confirm: prints then executes.
run() {
    local desc="$1"; shift
    if [[ "$CONFIRM" -eq 1 ]]; then
        log "$desc"
        printf '  $ %s\n' "$*"
        "$@"
    else
        log "[DRY-RUN] $desc"
        printf '  would run: %s\n' "$*"
    fi
}

# --- Preflight (read-only; always runs) -------------------------------------
log "Master-Data Service deploy"
if [[ "$CONFIRM" -eq 1 ]]; then
    log "MODE: APPLY"
else
    log "MODE: DRY-RUN (pass --confirm to apply)"
fi
log "checkout : $MDS_DIR"
log "venv     : $MDS_VENV"
log "service  : $MDS_SERVICE"
log "health   : $MDS_HEALTH_URL"
log "reqs     : $MDS_PY_REQ"

[[ -f "$MDS_DIR/manage.py" ]]   || { echo "ERROR: manage.py not found in $MDS_DIR" >&2; exit 1; }
[[ -x "$PY" ]]                  || { echo "ERROR: python not found at $PY (create the venv first)" >&2; exit 1; }
[[ -f "$MDS_DIR/$MDS_PY_REQ" ]] || { echo "ERROR: $MDS_PY_REQ not found in $MDS_DIR" >&2; exit 1; }

# Warn (do not fail) if the prod env clearly is not set — real deploy uses the
# systemd EnvironmentFile, so these may legitimately be empty in this shell.
if [[ "${DEBUG:-}" == "True" || "${DEBUG:-}" == "true" ]]; then
    warn "DEBUG is truthy in this shell — production must run with DEBUG=False."
fi

cd "$MDS_DIR"

# --- 1. Dependencies (idempotent) -------------------------------------------
run "1/5 Install/upgrade production dependencies" \
    "$PIP" install -r "$MDS_PY_REQ"

# --- 2. Database migrations -------------------------------------------------
# Review migrations before a real deploy. This applies schema changes to the
# MDS DB only (its own database). Idempotent — no-op if already applied.
run "2/5 Apply database migrations" \
    "$PY" manage.py migrate --no-input

# --- 3. Collect admin static (whitenoise serves these; nginx may also) ------
run "3/5 Collect static files" \
    "$PY" manage.py collectstatic --no-input -v 0

# --- 4. Restart the service -------------------------------------------------
# systemd Type=notify + on-failure restart: if the new code fails to boot the
# unit stays failed (does not silently serve old code). Check status after.
run "4/5 Restart the MDS systemd service" \
    sudo systemctl restart "$MDS_SERVICE"

# --- 5. Health check (verify, with retries) ---------------------------------
if [[ "$CONFIRM" -eq 1 ]]; then
    log "5/5 Health check: $MDS_HEALTH_URL"
    ok=0
    for i in 1 2 3 4 5 6; do
        if curl -fsS --max-time 5 "$MDS_HEALTH_URL" >/dev/null 2>&1; then
            ok=1
            log "Health check passed (attempt $i)."
            break
        fi
        warn "health check attempt $i failed; retrying in 3s…"
        sleep 3
    done
    if [[ "$ok" -ne 1 ]]; then
        echo "ERROR: health check FAILED after retries. See ROLLBACK below." >&2
        echo >&2
        print_rollback >&2
        exit 1
    fi
    log "Deploy complete and healthy."
else
    log "[DRY-RUN] 5/5 would curl $MDS_HEALTH_URL (expect 200 {\"status\":\"ok\"})"
    log "Dry-run only. Re-run with --confirm to apply."
fi

# --- Rollback note ----------------------------------------------------------
if [[ "$CONFIRM" -eq 1 ]]; then
    print_rollback
fi
