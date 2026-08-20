#!/usr/bin/env bash
# Legacy production deployment entry point.
# Defaults intentionally preserve the previous single-command production flow.
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
STEP="argument parsing"
ENVIRONMENT="production" RELEASE_SHA="$(git -C "$PROJECT_ROOT" rev-parse HEAD)" DRY_RUN=0 PREFLIGHT_ONLY=0 CONFIRM_PRODUCTION=1 EXECUTE=1

# Historical production defaults. Environment variables may still override
# these values for a one-off target, but invoking this script with no arguments
# uses the original license-manager deployment destination.
DEPLOY_TARGET_HOST="${DEPLOY_TARGET_HOST:-143.110.252.201}"
DEPLOY_TARGET_USER="${DEPLOY_TARGET_USER:-django}"
DEPLOY_REMOTE_ROOT="${DEPLOY_REMOTE_ROOT:-/home/django/license-manager}"
DEPLOY_KNOWN_HOSTS_FILE="${DEPLOY_KNOWN_HOSTS_FILE:-$HOME/.ssh/known_hosts}"
DEPLOY_BACKUP_COMMAND="${DEPLOY_BACKUP_COMMAND:-/home/django/license-manager/scripts/deployment/backup-db.sh}"
DEPLOY_WEB_SERVICE="${DEPLOY_WEB_SERVICE:-gunicorn}"
DEPLOY_WORKER_SERVICE="${DEPLOY_WORKER_SERVICE:-celery}"
DEPLOY_BEAT_SERVICE="${DEPLOY_BEAT_SERVICE:-celery-beat}"
DEPLOY_HEALTH_URL="${DEPLOY_HEALTH_URL:-https://license-manager.duckdns.org/api/health/}"

on_error() {
    local status=$?
    printf 'Deployment stopped during %s (exit %s). No secrets are printed.\n' "$STEP" "$status" >&2
    exit "$status"
}
trap on_error ERR
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }
usage() {
    cat <<'EOF'
Usage:
  scripts/deployment/auto-deploy.sh --environment staging|production --release-sha SHA [options]

Required:
  --environment NAME          Explicit target: staging or production
  --release-sha SHA           Full immutable Git commit SHA

Safety options:
  --dry-run                   Print the validated plan (default; no mutation)
  --preflight-only            Run remote preflight only (requires --execute)
  --execute                   Permit a non-dry-run deployment
  --confirm-production        Required for production execution
  --help                      Show this help

Target configuration must be injected by the deployment environment:
  DEPLOY_TARGET_HOST, DEPLOY_TARGET_USER, DEPLOY_REMOTE_ROOT,
  DEPLOY_KNOWN_HOSTS_FILE, DEPLOY_BACKUP_COMMAND, DEPLOY_WEB_SERVICE,
  DEPLOY_WORKER_SERVICE, DEPLOY_BEAT_SERVICE, DEPLOY_HEALTH_URL.

DEPLOY_BACKUP_COMMAND is a pre-provisioned absolute executable on the target.
This script never automatically reverses database migrations. Use the runbook's
forward-fix or restore procedure if a post-migration deployment fails.
EOF
}
require_command() { command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"; }
require_var() { [[ -n "${!1:-}" ]] || die "Required environment variable is missing: $1"; }
valid_service_name() { [[ "$1" =~ ^[A-Za-z0-9_.@-]+$ ]]; }
valid_absolute_command() { [[ "$1" == /* && "$1" != *$'\n'* && "$1" != *$'\r'* ]]; }
valid_https_url() { [[ "$1" =~ ^https://[^[:space:]]+$ ]]; }

while (($#)); do
    case "$1" in
        --environment) (($# >= 2)) || die '--environment requires a value'; ENVIRONMENT=$2; shift 2 ;;
        --release-sha) (($# >= 2)) || die '--release-sha requires a value'; RELEASE_SHA=$2; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --preflight-only) PREFLIGHT_ONLY=1; shift ;;
        --execute) EXECUTE=1; DRY_RUN=0; shift ;;
        --confirm-production) CONFIRM_PRODUCTION=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) die "Unknown argument: $1" ;;
    esac
done

[[ "$ENVIRONMENT" == staging || "$ENVIRONMENT" == production ]] || die '--environment must be staging or production'
[[ -n "$RELEASE_SHA" ]] || die '--release-sha is required'
[[ "$RELEASE_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || die '--release-sha must be a full 40-character commit SHA'
if [[ "$ENVIRONMENT" == production && "$EXECUTE" -eq 1 && "$CONFIRM_PRODUCTION" -ne 1 ]]; then die 'Production execution requires --confirm-production'; fi
if [[ "$CONFIRM_PRODUCTION" -eq 1 && "$ENVIRONMENT" != production ]]; then die '--confirm-production is valid only for production'; fi
if [[ "$PREFLIGHT_ONLY" -eq 1 && "$EXECUTE" -ne 1 ]]; then die '--preflight-only requires --execute'; fi

STEP="repository validation"
[[ "$(pwd -P)" == "$PROJECT_ROOT" ]] || die "Run from repository root: $PROJECT_ROOT"
[[ "$(git rev-parse --show-toplevel 2>/dev/null || true)" == "$PROJECT_ROOT" ]] || die 'Incorrect repository root'
[[ ! -e "$PROJECT_ROOT/.git/MERGE_HEAD" && ! -e "$PROJECT_ROOT/.git/CHERRY_PICK_HEAD" && ! -e "$PROJECT_ROOT/.git/REVERT_HEAD" ]] || die 'Unresolved Git operation'
git cat-file -e "${RELEASE_SHA}^{commit}" 2>/dev/null || die 'Release SHA is not a locally known commit'
[[ "$(git rev-parse "$RELEASE_SHA")" == "$RELEASE_SHA" ]] || die 'Release SHA did not resolve exactly'
git diff --quiet --ignore-submodules -- || die 'Dirty release source: deploy from a clean checkout'
git diff --cached --quiet --ignore-submodules || die 'Staged release content differs from HEAD'

STEP="local dependency validation"
require_command git; require_command ssh; require_command curl; require_command df
STEP="target configuration validation"
for name in DEPLOY_TARGET_HOST DEPLOY_TARGET_USER DEPLOY_REMOTE_ROOT DEPLOY_KNOWN_HOSTS_FILE DEPLOY_BACKUP_COMMAND DEPLOY_WEB_SERVICE DEPLOY_WORKER_SERVICE DEPLOY_BEAT_SERVICE DEPLOY_HEALTH_URL; do require_var "$name"; done
[[ "${DEPLOY_TARGET_HOST}" != *[[:space:]]* && "${DEPLOY_TARGET_USER}" != *[[:space:]]* ]] || die 'Deployment host and user must not contain whitespace'
[[ "$DEPLOY_REMOTE_ROOT" == /* && "$DEPLOY_REMOTE_ROOT" != *$'\n'* ]] || die 'DEPLOY_REMOTE_ROOT must be an absolute single-line path'
[[ -r "$DEPLOY_KNOWN_HOSTS_FILE" ]] || die 'DEPLOY_KNOWN_HOSTS_FILE must name a readable pinned known-hosts file'
valid_absolute_command "$DEPLOY_BACKUP_COMMAND" || die 'DEPLOY_BACKUP_COMMAND must be an absolute single-line target executable path'
for service in "$DEPLOY_WEB_SERVICE" "$DEPLOY_WORKER_SERVICE" "$DEPLOY_BEAT_SERVICE"; do valid_service_name "$service" || die 'Service names contain invalid characters'; done
valid_https_url "$DEPLOY_HEALTH_URL" || die 'DEPLOY_HEALTH_URL must be an HTTPS URL'
if [[ "$EXECUTE" -eq 1 ]]; then
    for name in DJANGO_SECRET_KEY DATABASE_URL REDIS_URL CELERY_BROKER_URL CELERY_RESULT_BACKEND ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS; do require_var "$name"; done
fi

info "Deployment target: $ENVIRONMENT"
info "Release SHA: ${RELEASE_SHA:0:12}"
[[ "$DRY_RUN" -eq 1 ]] && info 'Mode: dry-run (no mutation)' || info 'Mode: execute'
remote() { ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$DEPLOY_KNOWN_HOSTS_FILE" "${DEPLOY_TARGET_USER}@${DEPLOY_TARGET_HOST}" "$@"; }

STEP="preflight"
info 'Plan: validate target release, disk, backup command, migration plan, and service definitions.'
if [[ "$DRY_RUN" -eq 1 ]]; then
    info 'Dry-run complete: no backup, migration, checkout, restart, or network request was made.'
    exit 0
fi
remote bash -s -- "$DEPLOY_REMOTE_ROOT" "$RELEASE_SHA" "$DEPLOY_BACKUP_COMMAND" "$DEPLOY_WEB_SERVICE" "$DEPLOY_WORKER_SERVICE" "$DEPLOY_BEAT_SERVICE" <<'REMOTE_PREFLIGHT'
set -Eeuo pipefail
root=$1 sha=$2 backup=$3 web=$4 worker=$5 beat=$6
test -d "$root/.git"
git -C "$root" diff --quiet --ignore-submodules --
git -C "$root" diff --cached --quiet --ignore-submodules
git -C "$root" cat-file -e "${sha}^{commit}"
test -x "$backup"
df -Pk "$root" | awk 'NR == 2 { exit ($4 >= 1048576 ? 0 : 1) }'
for service in "$web" "$worker" "$beat"; do systemctl show "$service" >/dev/null; done
REMOTE_PREFLIGHT
if [[ "$PREFLIGHT_ONLY" -eq 1 ]]; then info 'Preflight passed. No release activation, backup, migration, or restart was performed.'; exit 0; fi

STEP="database backup"
remote bash -s -- "$DEPLOY_BACKUP_COMMAND" <<'REMOTE_BACKUP'
set -Eeuo pipefail
backup=$1
"$backup"
REMOTE_BACKUP
STEP="release activation and migration"
remote bash -s -- "$DEPLOY_REMOTE_ROOT" "$RELEASE_SHA" <<'REMOTE_RELEASE'
set -Eeuo pipefail
root=$1 sha=$2
git -C "$root" checkout --detach "$sha"
test "$(git -C "$root" rev-parse HEAD)" = "$sha"
cd "$root/backend"
python manage.py check --deploy
python manage.py migrate --plan
python manage.py migrate --noinput
python manage.py collectstatic --noinput
REMOTE_RELEASE
STEP="service activation"
remote bash -s -- "$DEPLOY_WEB_SERVICE" "$DEPLOY_WORKER_SERVICE" "$DEPLOY_BEAT_SERVICE" <<'REMOTE_SERVICES'
set -Eeuo pipefail
systemctl restart "$1"
systemctl restart "$2"
systemctl restart "$3"
for service in "$@"; do systemctl is-active --quiet "$service"; done
REMOTE_SERVICES
STEP="health verification"
curl --fail --silent --show-error --connect-timeout 5 --max-time 20 "$DEPLOY_HEALTH_URL" >/dev/null
remote bash -s -- "$DEPLOY_REMOTE_ROOT" "$RELEASE_SHA" <<'REMOTE_CONFIRM'
set -Eeuo pipefail
test "$(git -C "$1" rev-parse HEAD)" = "$2"
REMOTE_CONFIRM
info "Deployment succeeded: $ENVIRONMENT ${RELEASE_SHA:0:12}"
info 'If a migration makes rollback unsafe, do not reverse it automatically; use the documented forward-fix or restore procedure.'
