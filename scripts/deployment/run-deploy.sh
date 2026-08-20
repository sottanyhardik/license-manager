#!/usr/bin/env bash
# Compatibility launcher for the fail-closed deployment interface.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$HERE/auto-deploy.sh" "$@"
