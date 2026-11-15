#!/usr/bin/env bash
# License Manager Apple-Silicon developer workstation bootstrap
# Usage:
#   bash install-dev-workstation.sh [REPOSITORY_PATH]
#   bash install-dev-workstation.sh "$HOME/path/to/license-manager"
#
# Safe defaults:
# - Does not reset/clean/stash/checkout Git branches.
# - Does not overwrite existing .env files or Docker Compose files.
# - Does not run migrations or touch production services.
# - Installs project dependencies only from existing lock/requirements files.

set -Eeuo pipefail

REPO="${1:-$PWD}"
LOG_DIR="${HOME}/Library/Logs/license-manager-dev-setup"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\n\033[1;33mWARNING: %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

[[ "$(uname -s)" == "Darwin" ]] || fail "This installer is for macOS."
[[ "$(uname -m)" == "arm64" ]] || warn "This Mac is not reporting arm64; Homebrew paths may differ."
[[ -d "$REPO" ]] || fail "Repository path does not exist: $REPO"
REPO="$(cd "$REPO" && pwd -P)"

say "Machine inventory"
sw_vers
uname -a
sysctl -n hw.memsize | awk '{printf "RAM: %.1f GB\n", $1/1073741824}'
df -h /

if ! have brew; then
  say "Installing Homebrew"
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    grep -q 'brew shellenv' "$HOME/.zprofile" 2>/dev/null || \
      printf '\neval "$(/opt/homebrew/bin/brew shellenv)"\n' >> "$HOME/.zprofile"
  else
    fail "Homebrew installation did not produce /opt/homebrew/bin/brew."
  fi
fi

say "Updating Homebrew"
brew update

say "Installing command-line developer tools"
brew install \
  git gh jq yq ripgrep fd fzf bat eza tmux tree wget curl \
  openssl@3 readline zlib xz pkg-config \
  pre-commit gitleaks trivy shellcheck shfmt \
  libpq

say "Installing pinned database and runtime tools"
brew install postgresql@16 redis

# mise manages language runtimes without replacing system Python/Node.
brew install mise
if ! grep -q 'mise activate zsh' "$HOME/.zshrc" 2>/dev/null; then
  printf '\neval "$(mise activate zsh)"\n' >> "$HOME/.zshrc"
fi
eval "$(mise activate bash)"

say "Installing Python 3.14, Node.js 24 and Java 21 via mise"
mise use --global python@3.14
mise use --global node@24
mise use --global java@21

say "Installing GUI applications"
brew install --cask docker
brew install --cask pycharm
brew install --cask claude-code

say "Checking repository and preserving current Git state"
cd "$REPO"
git rev-parse --show-toplevel >/dev/null 2>&1 || fail "Not a Git repository: $REPO"
git status --short
printf 'Branch: '
git branch --show-current
printf 'Root: %s\n' "$REPO"

say "Checking project structure"
for d in backend frontend master-data-service mds-client; do
  if [[ -d "$REPO/$d" ]]; then
    printf 'Found: %s\n' "$d"
  else
    printf 'Not present: %s\n' "$d"
  fi
done

say "Installing frontend dependencies from the existing lockfile"
if [[ -d "$REPO/frontend" ]]; then
  if [[ -f "$REPO/frontend/package-lock.json" ]]; then
    (cd "$REPO/frontend" && npm ci)
  elif [[ -f "$REPO/frontend/pnpm-lock.yaml" ]]; then
    warn "pnpm lockfile detected; enabling pnpm with Corepack."
    corepack enable
    (cd "$REPO/frontend" && pnpm install --frozen-lockfile)
  elif [[ -f "$REPO/frontend/yarn.lock" ]]; then
    warn "Yarn lockfile detected; enabling Corepack."
    corepack enable
    (cd "$REPO/frontend" && yarn install --immutable)
  else
    warn "No frontend lockfile found. Not running an unpinned install."
  fi
fi

say "Creating backend virtual environment and installing declared test dependencies"
if [[ -d "$REPO/backend" ]]; then
  if [[ ! -d "$REPO/backend/.venv" ]]; then
    (cd "$REPO/backend" && python -m venv .venv)
  fi
  if [[ -f "$REPO/backend/requirements-test.txt" ]]; then
    (cd "$REPO/backend" && .venv/bin/python -m pip install --upgrade pip && \
      .venv/bin/python -m pip install -r requirements-test.txt)
  elif [[ -f "$REPO/backend/requirements.txt" ]]; then
    (cd "$REPO/backend" && .venv/bin/python -m pip install --upgrade pip && \
      .venv/bin/python -m pip install -r requirements.txt)
  else
    warn "No backend requirements file found; left virtualenv ready without guessing dependencies."
  fi
fi

say "Installing MDS test dependencies if declared"
if [[ -d "$REPO/master-data-service" ]]; then
  if [[ ! -d "$REPO/master-data-service/.venv" ]]; then
    (cd "$REPO/master-data-service" && python -m venv .venv)
  fi
  if [[ -f "$REPO/master-data-service/requirements-test.txt" ]]; then
    (cd "$REPO/master-data-service" && .venv/bin/python -m pip install --upgrade pip && \
      .venv/bin/python -m pip install -r requirements-test.txt)
  elif [[ -f "$REPO/master-data-service/requirements.txt" ]]; then
    (cd "$REPO/master-data-service" && .venv/bin/python -m pip install --upgrade pip && \
      .venv/bin/python -m pip install -r requirements.txt)
  fi
fi

say "Preparing mds-client virtual environment"
if [[ -d "$REPO/mds-client" ]]; then
  if [[ ! -d "$REPO/mds-client/.venv" ]]; then
    (cd "$REPO/mds-client" && python -m venv .venv)
  fi
  (cd "$REPO/mds-client" && .venv/bin/python -m pip install --upgrade pip)
  # Follow the repository CI's explicit dependencies; do not install into global Python.
  (cd "$REPO/mds-client" && .venv/bin/python -m pip install 'Django>=6' requests)
fi

say "Starting Docker Desktop"
open -a Docker || warn "Could not launch Docker Desktop automatically."
echo "Waiting up to 120 seconds for Docker daemon..."
for _ in $(seq 1 60); do
  if docker info >/dev/null 2>&1; then break; fi
  sleep 2
done
if docker info >/dev/null 2>&1; then
  docker version
  docker compose version
else
  warn "Docker daemon is not ready. Open Docker Desktop, accept its first-run prompts, then rerun this script."
fi

say "Checking for existing Compose configuration"
if [[ -f "$REPO/compose.yaml" || -f "$REPO/compose.yml" || -f "$REPO/docker-compose.yml" || -f "$REPO/docker-compose.yaml" ]]; then
  echo "Existing Compose file found. It was preserved; inspect it before starting services."
else
  warn "No Compose file found at repository root. This installer will not invent database credentials or overwrite project architecture."
fi

say "Installing optional Python developer tools in backend virtualenv"
if [[ -x "$REPO/backend/.venv/bin/python" ]]; then
  "$REPO/backend/.venv/bin/python" -m pip install ruff pytest-cov bandit
fi

say "Installing Claude Code health checks"
if have claude; then
  claude --version
  claude doctor || true
else
  warn "Claude Code cask was installed but command is not yet on PATH. Open a new terminal and run: claude"
fi

say "Final tool versions"
for cmd in brew git gh mise python node npm java docker claude psql redis-cli; do
  if have "$cmd"; then
    printf '%-12s' "$cmd"
    case "$cmd" in
      docker) docker --version ;;
      claude) claude --version ;;
      psql) psql --version ;;
      redis-cli) redis-cli --version ;;
      *) "$cmd" --version 2>/dev/null | head -n 1 || true ;;
    esac
  else
    printf '%-12s not on PATH (may require a new terminal)\n' "$cmd"
  fi
done

say "Setup finished (installation is not the same as application validation)"
cat <<EOF
Repository: $REPO
Log:        $LOG_FILE

Next steps:
1. Open a new Terminal window so PATH and mise changes load.
2. Open Docker Desktop and complete any first-run prompts.
3. Inspect the repository's existing Compose file and environment settings.
4. Start only the existing local development services.
5. Run the repository's CI commands before declaring the setup complete.

No production database was contacted. No migrations were run. No Git branch, commit,
push, merge, reset, clean, or stash operation was performed.
EOF
