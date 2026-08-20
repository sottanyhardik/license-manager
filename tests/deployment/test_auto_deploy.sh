#!/usr/bin/env bash
# Mock-only contract tests for scripts/deployment/auto-deploy.sh.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SHA=0123456789012345678901234567890123456789
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
: > "$TMP/known_hosts"
CANDIDATE="$TMP/repo"
mkdir -p "$CANDIDATE/scripts/deployment"
cp "$ROOT/scripts/deployment/auto-deploy.sh" "$CANDIDATE/scripts/deployment/"
git -C "$CANDIDATE" init -q
git -C "$CANDIDATE" add scripts/deployment/auto-deploy.sh
git -C "$CANDIDATE" -c user.name=test -c user.email=test@example.invalid commit -qm fixture
SCRIPT="$CANDIDATE/scripts/deployment/auto-deploy.sh"
SHA="$(git -C "$CANDIDATE" rev-parse HEAD)"
cat > "$TMP/bin/ssh" <<'EOF'
#!/usr/bin/env bash
count_file="${DEPLOY_TEST_TMP}/ssh-count"
count=0; [[ -f "$count_file" ]] && count=$(cat "$count_file")
count=$((count + 1)); printf '%s' "$count" > "$count_file"
if [[ "${SSH_FAIL_CALL:-0}" == "$count" ]]; then exit 42; fi
cat >/dev/null || true
EOF
cat > "$TMP/bin/curl" <<'EOF'
#!/usr/bin/env bash
[[ "${CURL_FAIL:-0}" == 1 ]] && exit 41
exit 0
EOF
chmod +x "$TMP/bin/"{ssh,curl}
base_env=(
  "PATH=$TMP/bin:$PATH" "DEPLOY_TEST_TMP=$TMP"
  "DEPLOY_TARGET_HOST=staging.example.invalid" "DEPLOY_TARGET_USER=deployer"
  "DEPLOY_REMOTE_ROOT=/srv/license-manager" "DEPLOY_KNOWN_HOSTS_FILE=$TMP/known_hosts"
  "DEPLOY_BACKUP_COMMAND=/usr/local/bin/backup-license-manager"
  "DEPLOY_WEB_SERVICE=license-web" "DEPLOY_WORKER_SERVICE=license-worker"
  "DEPLOY_BEAT_SERVICE=license-beat" "DEPLOY_HEALTH_URL=https://staging.example.invalid/api/health/"
  "DJANGO_SECRET_KEY=placeholder" "DATABASE_URL=postgres://placeholder"
  "REDIS_URL=redis://placeholder" "CELERY_BROKER_URL=redis://placeholder"
  "CELERY_RESULT_BACKEND=redis://placeholder" "ALLOWED_HOSTS=staging.example.invalid"
  "CSRF_TRUSTED_ORIGINS=https://staging.example.invalid"
)
run() { (cd "$CANDIDATE" && env "${base_env[@]}" "$@"); }
expect_ok() { "$@"; }
expect_fail() { if "$@"; then echo "expected failure: $*" >&2; exit 1; fi; }
expect_ok bash "$SCRIPT" --help
expect_fail run bash "$SCRIPT" --release-sha "$SHA"
expect_fail run bash "$SCRIPT" --environment invalid --release-sha "$SHA"
expect_fail run bash "$SCRIPT" --environment staging
expect_fail run bash "$SCRIPT" --environment production --release-sha "$SHA" --execute
expect_ok run bash "$SCRIPT" --environment production --release-sha "$SHA" --confirm-production
expect_ok run bash "$SCRIPT" --environment staging --release-sha "$SHA" --dry-run
expect_fail bash -c 'cd "$1" && env "${@:2}"' _ "$CANDIDATE" "${base_env[@]}" DEPLOY_HEALTH_URL= bash "$SCRIPT" --environment staging --release-sha "$SHA"
expect_ok run bash "$SCRIPT" --environment staging --release-sha "$SHA" --preflight-only --execute
rm -f "$TMP/ssh-count"
expect_fail bash -c 'cd "$1" && env "${@:2}"' _ "$CANDIDATE" "${base_env[@]}" DEPLOY_TEST_TMP="$TMP" SSH_FAIL_CALL=2 bash "$SCRIPT" --environment staging --release-sha "$SHA" --execute
rm -f "$TMP/ssh-count"
expect_fail bash -c 'cd "$1" && env "${@:2}"' _ "$CANDIDATE" "${base_env[@]}" DEPLOY_TEST_TMP="$TMP" SSH_FAIL_CALL=3 bash "$SCRIPT" --environment staging --release-sha "$SHA" --execute
rm -f "$TMP/ssh-count"
expect_fail bash -c 'cd "$1" && env "${@:2}"' _ "$CANDIDATE" "${base_env[@]}" DEPLOY_TEST_TMP="$TMP" SSH_FAIL_CALL=4 bash "$SCRIPT" --environment staging --release-sha "$SHA" --execute
rm -f "$TMP/ssh-count"
expect_fail bash -c 'cd "$1" && env "${@:2}"' _ "$CANDIDATE" "${base_env[@]}" DEPLOY_TEST_TMP="$TMP" CURL_FAIL=1 bash "$SCRIPT" --environment staging --release-sha "$SHA" --execute
echo "auto-deploy mock contract tests: passed"
