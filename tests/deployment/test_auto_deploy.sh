#!/usr/bin/env bash
# Mock-only zero-argument contract tests for the established auto deploy flow.
# No command in this file opens a network connection or uses a real credential.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/repo/scripts/deployment"
cp "$ROOT/scripts/deployment/auto-deploy.sh" "$TMP/repo/scripts/deployment/"
git -C "$TMP/repo" init -q
git -C "$TMP/repo" add scripts/deployment/auto-deploy.sh
git -C "$TMP/repo" -c user.name=test -c user.email=test@example.invalid commit -qm fixture
SCRIPT="$TMP/repo/scripts/deployment/auto-deploy.sh"

cat > "$TMP/bin/ssh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'ssh\n' >> "$DEPLOY_TEST_EVENTS"
printf '%s\n' "$*" >> "$DEPLOY_TEST_SSH_ARGS"
count=$(grep -c '^' "$DEPLOY_TEST_EVENTS")
cat >/dev/null || true
[[ "${MOCK_SSH_FAILURE_EVENT:-0}" != "$count" ]] || exit 42
EOF
cat > "$TMP/bin/scp" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'scp\n' >> "$DEPLOY_TEST_EVENTS"
EOF
cat > "$TMP/bin/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'curl\n' >> "$DEPLOY_TEST_EVENTS"
printf '200'
EOF
chmod +x "$TMP/bin/ssh" "$TMP/bin/scp" "$TMP/bin/curl"

run_deploy() {
  (
    cd "$TMP/repo"
    # A tracked modification is intentional: the operator contract must not
    # reject a normal dirty worktree or alter it in order to proceed.
    printf 'operator change\n' >> deployment-note.txt
    env PATH="$TMP/bin:$PATH" \
      DEPLOY_TEST_EVENTS="$TMP/events" \
      DEPLOY_TEST_SSH_ARGS="$TMP/ssh-args" \
      DEPLOY_PASSWORD='not-a-real-secret' \
      bash "$SCRIPT" </dev/null
  )
}

rm -f "$TMP/events" "$TMP/ssh-args"
run_deploy >"$TMP/output" 2>&1

# Three configured servers, with one remote deploy then one health check each.
[[ $(grep -c '^ssh$' "$TMP/events") -eq 3 ]]
[[ $(grep -c '^curl$' "$TMP/events") -eq 3 ]]
[[ $(wc -l < "$TMP/ssh-args") -eq 3 ]]
[[ $(sed -n '1p' "$TMP/events") == ssh ]]
[[ $(sed -n '2p' "$TMP/events") == curl ]]
[[ $(sed -n '3p' "$TMP/events") == ssh ]]
[[ $(sed -n '4p' "$TMP/events") == curl ]]
[[ $(sed -n '5p' "$TMP/events") == ssh ]]
[[ $(sed -n '6p' "$TMP/events") == curl ]]
! grep -Fq 'not-a-real-secret' "$TMP/output"

# One transient remote-stage failure is repaired automatically by rerunning the
# idempotent deployment for that server.
rm -f "$TMP/events" "$TMP/ssh-args"
(
  cd "$TMP/repo"
  env PATH="$TMP/bin:$PATH" \
    DEPLOY_TEST_EVENTS="$TMP/events" \
    DEPLOY_TEST_SSH_ARGS="$TMP/ssh-args" \
    DEPLOY_PASSWORD='not-a-real-secret' \
    MOCK_SSH_FAILURE_EVENT=3 \
    bash "$SCRIPT" </dev/null
) >"$TMP/recovery-output" 2>&1
grep -Fq 'retrying automatic repair' "$TMP/recovery-output"
[[ $(grep -c '^ssh$' "$TMP/events") -eq 4 ]]
! grep -Fq 'not-a-real-secret' "$TMP/recovery-output"

echo 'auto-deploy zero-argument mock contract: passed'
