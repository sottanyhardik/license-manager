#!/usr/bin/env bash
# Compatibility launcher.  Preflight is performed by the sole deployment
# entry point so validation cannot diverge from rollout behavior.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$HERE/auto-deploy.sh" "$@" --preflight-only --execute
