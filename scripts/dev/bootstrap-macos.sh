#!/bin/bash
# One-time developer-machine bootstrap for the License Manager (macOS, Apple Silicon).
# Run it yourself in Terminal (it needs your password once, for Homebrew):
#     bash scripts/dev/bootstrap-macos.sh [--with-ecc-plugin] [--skip-db]
# Idempotent: safe to re-run. Installs only LOCAL dev tooling; touches no remote system.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WITH_ECC_PLUGIN=0; SKIP_DB=0
for a in "$@"; do case $a in --with-ecc-plugin) WITH_ECC_PLUGIN=1;; --skip-db) SKIP_DB=1;; esac; done
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "1/9 Xcode command line tools"
xcode-select -p >/dev/null 2>&1 || { xcode-select --install; echo "Re-run this script after the CLT installer finishes."; exit 1; }

step "2/9 Homebrew"
if ! command -v brew >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/brew ]; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
eval "$(/opt/homebrew/bin/brew shellenv)"

step "3/9 CLI toolchain (node 24, gh, uv, postgres 16, redis, ripgrep, jq)"
brew install node@24 gh uv postgresql@16 redis ripgrep jq
brew link --overwrite --force node@24 >/dev/null 2>&1 || true

step "4/9 Shell PATH (~/.zshrc)"
touch ~/.zshrc
add_line() { grep -qxF "$1" ~/.zshrc || echo "$1" >> ~/.zshrc; }
add_line 'eval "$(/opt/homebrew/bin/brew shellenv)"'
add_line 'export PATH="$HOME/.local/bin:/opt/homebrew/opt/node@24/bin:/opt/homebrew/opt/postgresql@16/bin:$PATH"'
export PATH="$HOME/.local/bin:/opt/homebrew/opt/node@24/bin:/opt/homebrew/opt/postgresql@16/bin:$PATH"

step "5/9 Claude Code (native installer already present at ~/.local/bin/claude?)"
if ! command -v claude >/dev/null 2>&1; then curl -fsSL https://claude.ai/install.sh | bash; fi
claude --version

step "6/9 Python 3.14 venv (.venv-3.14) + backend/MDS test deps — matches CI"
uv python install 3.14
[ -d "$ROOT/.venv-3.14" ] || uv venv "$ROOT/.venv-3.14" --python 3.14
uv pip install --python "$ROOT/.venv-3.14/bin/python" -r "$ROOT/backend/requirements-test.txt"
uv pip install --python "$ROOT/.venv-3.14/bin/python" -r "$ROOT/master-data-service/requirements-test.txt"
uv pip install --python "$ROOT/.venv-3.14/bin/python" "Django>=6" requests
echo "In PyCharm: Settings → Python Interpreter → Add → Existing → $ROOT/.venv-3.14/bin/python"

step "7/9 Frontend deps (npm ci)"
(cd "$ROOT/frontend" && npm ci)

if [ $SKIP_DB -eq 0 ]; then
  step "8/9 Local Postgres 16 + Redis, CI-identical dev/test databases"
  brew services start postgresql@16
  brew services start redis
  for i in $(seq 1 20); do pg_isready -q -h localhost && break; sleep 1; done
  mk() { # role/db name
    psql -h localhost -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$1'" | grep -q 1 \
      || psql -h localhost -d postgres -c "CREATE ROLE $1 LOGIN PASSWORD '$1' CREATEDB"
    psql -h localhost -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$1'" | grep -q 1 \
      || psql -h localhost -d postgres -c "CREATE DATABASE $1 OWNER $1"
  }
  mk lmanagement; mk master_data
else
  step "8/9 skipped databases (--skip-db)"
fi

step "9/9 Claude Code integrations"
PYCHARM="/Applications/PyCharm.app/Contents/MacOS/pycharm"
if pgrep -xq pycharm; then
  echo "PyCharm is running — install the plugin from Settings → Plugins → Marketplace → 'Claude Code', then restart."
elif [ -x "$PYCHARM" ]; then
  "$PYCHARM" installPlugins com.anthropic.code.plugin || echo "Install 'Claude Code' from Settings → Plugins → Marketplace."
fi
if [ $WITH_ECC_PLUGIN -eq 1 ]; then
  # Full ECC plugin (71 agents / 314 skills / Node hooks). Project scope only, minimal hook profile.
  (cd "$ROOT" && claude plugin marketplace add https://github.com/affaan-m/ECC && claude plugin install ecc@ecc --scope project)
fi

step "Done. Verify with: sh scripts/dev/doctor.sh && sh scripts/dev/quality-gate.sh all"
echo "Open a NEW terminal (or 'source ~/.zshrc') so PATH changes apply."
