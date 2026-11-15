#!/usr/bin/env bash
# One-time workstation bootstrap for Apple Silicon macOS. Idempotent; safe to re-run.
# Installs only what is missing. Never touches databases or deploy config.
#
#   1. uv + Python 3.14 (arm64, user space)        → ~/.local/bin, ~/.local/share/uv
#   2. Node.js 24 LTS (arm64, user space)          → ~/.local/node
#   3. Homebrew CLI tools from ./Brewfile          (needs Homebrew — see below)
#   4. backend/.venv + master-data-service/.venv from the pinned requirements
#   5. frontend: npm ci
#   6. local env files (scripts/dev/init-local-env.sh)
#
# Homebrew and Docker Desktop's first launch need your macOS password, so they are
# NOT automated here. Install Homebrew first (official command):
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
export PATH="$HOME/.local/bin:$HOME/.local/node/bin:/opt/homebrew/bin:$PATH"
[ "$(uname -m)" = arm64 ] || { echo "expected Apple Silicon (arm64)"; exit 1; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# 1. uv + Python 3.14
if ! command -v uv >/dev/null; then
  v=$(curl -fsSL https://api.github.com/repos/astral-sh/uv/releases/latest | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')
  f=uv-aarch64-apple-darwin.tar.gz
  (cd "$TMP" && curl -fsSLO "https://github.com/astral-sh/uv/releases/download/$v/$f" \
     && curl -fsSLO "https://github.com/astral-sh/uv/releases/download/$v/$f.sha256" \
     && shasum -a 256 -c "$f.sha256" && tar xzf "$f")
  mkdir -p ~/.local/bin && cp "$TMP"/uv-aarch64-apple-darwin/uv{,x} ~/.local/bin/
fi
uv python install 3.14
PY314=$(uv python find 3.14)
command -v ruff >/dev/null || uv tool install ruff

# 2. Node 24
if ! ~/.local/node/bin/node -v 2>/dev/null | grep -q '^v24\.'; then
  base=https://nodejs.org/dist/latest-v24.x
  (cd "$TMP" && curl -fsSLO "$base/SHASUMS256.txt" \
     && f=$(grep -oE 'node-v24[0-9.]+-darwin-arm64\.tar\.gz' SHASUMS256.txt | head -1) \
     && curl -fsSLO "$base/$f" && grep " $f\$" SHASUMS256.txt | shasum -a 256 -c - && tar xzf "$f" \
     && rm -rf ~/.local/node && mv "${f%.tar.gz}" ~/.local/node)
fi

# 3. Homebrew tools
if command -v brew >/dev/null; then brew bundle --file="$ROOT/Brewfile"
else echo "!! Homebrew not installed — skipping Brewfile (gh, fd, fzf, direnv, libpq, redis-cli)."; fi

# 4. Python venvs (pinned manifests are authoritative; gunicorn pin mirrors master-data-service/requirements-prod.txt)
mkvenv() { # dir requirements
  if [ -x "$1/.venv/bin/python" ] && "$1/.venv/bin/python" -c 'import sys; sys.exit(sys.version_info < (3,14))'; then :; else
    [ -e "$1/.venv" ] && mv "$1/.venv" "$1/.venv.bak-$(date +%Y%m%d%H%M%S)"
    "$PY314" -m venv "$1/.venv"
  fi
  "$1/.venv/bin/python" -m pip install -q --upgrade pip
  uv pip install -q -r "$1/$2" --python "$1/.venv/bin/python"
}
mkvenv backend requirements-test.txt
uv pip install -q gunicorn==23.0.0 --python backend/.venv/bin/python
mkvenv master-data-service requirements-test.txt

# 5. Frontend
(cd frontend && npm ci)

# 6. Env files
scripts/dev/init-local-env.sh

echo
echo "Bootstrap done. Next: open Docker Desktop once, then scripts/dev-start.sh --migrate && scripts/dev-check.sh --gates all"
