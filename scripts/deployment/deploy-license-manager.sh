#!/usr/bin/env bash
# Deprecated compatibility entry point. It intentionally delegates to the
# fail-closed deployment interface rather than carrying a hard-coded host.
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$HERE/auto-deploy.sh" "$@"
