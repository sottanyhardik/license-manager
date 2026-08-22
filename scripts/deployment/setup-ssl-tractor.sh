#!/usr/bin/env bash
# Deprecated compatibility entry point.
#
# The historic one-off bootstrap embedded a production host, domain, and
# filesystem layout.  Certificate provisioning is infrastructure work and is
# intentionally not an executable release path from this repository.
set -Eeuo pipefail

cat >&2 <<'EOF'
setup-ssl-tractor.sh is retired because it contained a hard-coded production
target. Use scripts/deployment/auto-deploy.sh with an explicit environment,
immutable release SHA, pinned known-hosts file, and reviewed target config.
Certificate provisioning must be performed by the separately approved
infrastructure workflow. This command makes no network or system changes.
EOF
exit 2
