#!/usr/bin/env bash
# Fail-closed deployment entry point. It deliberately has no default host,
# branch, credential, or destructive operation.
set -Eeuo pipefail
IFS=$'\n\t'

usage() {
  cat <<'EOF'
Usage:
  scripts/deployment/auto-deploy.sh --environment staging|production \
    --release-sha <40-char-git-sha> [--dry-run|--execute] [--preflight-only] \
    [--confirm-production]

The default is dry-run. --execute performs a remote rollout after preflight,
backup, immutable checkout, migration/build, restart, and health checks.
Production execution additionally requires --confirm-production.
EOF
}

die() { printf 'deployment error: %s\n' "$*" >&2; exit 1; }
info() { printf 'deployment: %s\n' "$*"; }
require_env() { [[ -n "${!1:-}" ]] || die "required environment variable is missing: $1"; }

environment=""; release_sha=""; mode="dry-run"; preflight_only=false; confirm_production=false
while (($#)); do
  case "$1" in
    --environment) environment="${2:-}"; shift 2 ;;
    --release-sha) release_sha="${2:-}"; shift 2 ;;
    --dry-run) mode="dry-run"; shift ;;
    --execute) mode="execute"; shift ;;
    --preflight-only) preflight_only=true; shift ;;
    --confirm-production) confirm_production=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ "$environment" == "staging" || "$environment" == "production" ]] || die "--environment must be staging or production"
[[ "$release_sha" =~ ^[0-9a-fA-F]{40}$ ]] || die "--release-sha must be a full 40-character commit SHA"
if [[ "$mode" == "execute" && "$environment" == "production" && "$confirm_production" != true ]]; then
  die "production execution requires --confirm-production"
fi

# Application secrets stay in the remote service environment.  This launcher
# only accepts non-secret release-target configuration and never forwards
# credentials over SSH command arguments.
for name in DEPLOY_TARGET_HOST DEPLOY_TARGET_USER DEPLOY_REMOTE_ROOT DEPLOY_KNOWN_HOSTS_FILE DEPLOY_BACKUP_COMMAND DEPLOY_WEB_SERVICE DEPLOY_WORKER_SERVICE DEPLOY_BEAT_SERVICE DEPLOY_HEALTH_URL; do
  require_env "$name"
done

[[ -r "$DEPLOY_KNOWN_HOSTS_FILE" ]] || die "DEPLOY_KNOWN_HOSTS_FILE must be a readable pinned known-hosts file"
[[ "$DEPLOY_TARGET_HOST" != *[[:space:]]* ]] || die "DEPLOY_TARGET_HOST must not contain whitespace"
[[ "$DEPLOY_TARGET_USER" != *[[:space:]]* ]] || die "DEPLOY_TARGET_USER must not contain whitespace"
[[ "$DEPLOY_REMOTE_ROOT" == /* ]] || die "DEPLOY_REMOTE_ROOT must be an absolute path"
[[ "$DEPLOY_BACKUP_COMMAND" == /* ]] || die "DEPLOY_BACKUP_COMMAND must be an absolute executable path"
[[ "$DEPLOY_HEALTH_URL" =~ ^https:// ]] || die "DEPLOY_HEALTH_URL must use https"
[[ "$DEPLOY_HEALTH_URL" != *[[:space:]]* ]] || die "DEPLOY_HEALTH_URL must not contain whitespace"
for service in "$DEPLOY_WEB_SERVICE" "$DEPLOY_WORKER_SERVICE" "$DEPLOY_BEAT_SERVICE"; do
  [[ "$service" =~ ^[A-Za-z0-9@._-]+$ ]] || die "service names may contain only letters, digits, @, ., _, and -"
done
git cat-file -e "${release_sha}^{commit}" 2>/dev/null || die "release SHA is not present in the local repository: $release_sha"

ssh_args=(-o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$DEPLOY_KNOWN_HOSTS_FILE" -o ConnectTimeout=15 -o ServerAliveInterval=15 -o ServerAliveCountMax=2)
remote="${DEPLOY_TARGET_USER}@${DEPLOY_TARGET_HOST}"
remote_root_q=$(printf '%q' "$DEPLOY_REMOTE_ROOT")
sha_q=$(printf '%q' "$release_sha")
remote_runtime_env=""
for name in DEPLOY_BACKUP_COMMAND DEPLOY_WEB_SERVICE DEPLOY_WORKER_SERVICE DEPLOY_BEAT_SERVICE; do
  printf -v value_q '%q' "${!name}"
  remote_runtime_env+="${name}=${value_q} "
done

run_remote() {
  local label="$1" command="$2"
  info "$label"
  if [[ "$mode" == "dry-run" ]]; then
    printf '  remote command withheld in dry run\n'
    return 0
  fi
  ssh "${ssh_args[@]}" "$remote" "${remote_runtime_env}bash -lc $(printf '%q' "$command")"
}

preflight_command="set -Eeuo pipefail; test -d $remote_root_q; git -C $remote_root_q rev-parse --is-inside-work-tree >/dev/null; test -x \"\${DEPLOY_BACKUP_COMMAND}\""
backup_command="set -Eeuo pipefail; \"\${DEPLOY_BACKUP_COMMAND}\""
release_command="set -Eeuo pipefail; cd $remote_root_q; git fetch --tags --prune origin; git cat-file -e ${sha_q}^{commit}; git checkout --detach $sha_q; backend/.venv/bin/python backend/manage.py migrate --no-input; backend/.venv/bin/python backend/manage.py collectstatic --no-input; (cd frontend && npm ci --ignore-scripts && npm run build)"
restart_command="set -Eeuo pipefail; sudo systemctl restart \"\${DEPLOY_WEB_SERVICE}\"; sudo systemctl restart \"\${DEPLOY_WORKER_SERVICE}\"; sudo systemctl restart \"\${DEPLOY_BEAT_SERVICE}\""

info "environment=$environment release=$release_sha mode=$mode"
run_remote "preflight: remote repository and service configuration" "$preflight_command"
if [[ "$preflight_only" == true ]]; then
  info "preflight completed"
  exit 0
fi
run_remote "backup: create verified database checkpoint" "$backup_command"
run_remote "release: immutable checkout, migration, static collection, and frontend build" "$release_command"
run_remote "restart: explicitly configured services" "$restart_command"
if [[ "$mode" == "dry-run" ]]; then
  info "health: curl -fsS --max-time 20 $DEPLOY_HEALTH_URL"
else
  info "health: verifying deployment endpoint"
  curl --fail --silent --show-error --location --max-time 20 "$DEPLOY_HEALTH_URL" >/dev/null
fi
info "rollback: restore the verified backup and redeploy the prior immutable SHA; do not run destructive database commands."
info "deployment gate completed"
