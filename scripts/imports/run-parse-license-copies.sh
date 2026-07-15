#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Run parse_existing_license_copies management command on all 3 servers.
#
# Usage:
#   bash scripts/imports/run-parse-license-copies.sh                  # live run on all 3 servers
#   bash scripts/imports/run-parse-license-copies.sh --dry-run        # preview only
#   bash scripts/imports/run-parse-license-copies.sh --norm-desc-only # just fix export descriptions
#   bash scripts/imports/run-parse-license-copies.sh --license-number 0311005034  # single licence
#   bash scripts/imports/run-parse-license-copies.sh license-manager  # single server
#   bash scripts/imports/run-parse-license-copies.sh labdhi           # single server
#   bash scripts/imports/run-parse-license-copies.sh tractor          # single server
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_DIR="/home/django/license-manager"
VENV="$REPO_DIR/venv"
MANAGE="$VENV/bin/python $REPO_DIR/backend/manage.py"

# Servers: "label:ip" format
declare -a ALL_SERVERS=(
    "license-manager:143.110.252.201"
    "labdhi:139.59.92.226"
    "tractor:165.232.185.220"
)

# ── Parse args ──────────────────────────────────────────────────────────────
CMD_ARGS=""
TARGET_SERVER=""

for arg in "$@"; do
    case "$arg" in
        license-manager|labdhi|tractor)
            TARGET_SERVER="$arg"
            ;;
        --dry-run|--norm-desc-only|--parse-only)
            CMD_ARGS="$CMD_ARGS $arg"
            ;;
        --license-number=*)
            CMD_ARGS="$CMD_ARGS $arg"
            ;;
        --license-number)
            # next arg is the value — handled below
            CMD_ARGS="$CMD_ARGS $arg"
            ;;
        *)
            CMD_ARGS="$CMD_ARGS $arg"
            ;;
    esac
done

# ── Filter servers ───────────────────────────────────────────────────────────
declare -a SERVERS=()
if [[ -n "$TARGET_SERVER" ]]; then
    for entry in "${ALL_SERVERS[@]}"; do
        label="${entry%%:*}"
        if [[ "$label" == "$TARGET_SERVER" ]]; then
            SERVERS+=("$entry")
        fi
    done
    if [[ ${#SERVERS[@]} -eq 0 ]]; then
        echo "Unknown server '$TARGET_SERVER'. Choose: license-manager, labdhi, tractor"
        exit 1
    fi
else
    SERVERS=("${ALL_SERVERS[@]}")
fi

# ── Summary header ───────────────────────────────────────────────────────────
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║     parse_existing_license_copies — multi-server run      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
[[ -n "$CMD_ARGS" ]] && echo "  Options: $CMD_ARGS" || echo "  Options: (none — live run)"
echo "  Servers: ${#SERVERS[@]}"
echo ""

# ── Run on each server ───────────────────────────────────────────────────────
TOTAL_SERVERS=${#SERVERS[@]}
IDX=0

for entry in "${SERVERS[@]}"; do
    IDX=$((IDX + 1))
    LABEL="${entry%%:*}"
    IP="${entry##*:}"

    echo "┌─────────────────────────────────────────────────────────"
    echo "│ [$IDX/$TOTAL_SERVERS] $LABEL ($IP)"
    echo "└─────────────────────────────────────────────────────────"

    if ! ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
            django@"$IP" "echo '  SSH OK'" 2>/dev/null; then
        echo "  ✗ Cannot reach $LABEL — skipping"
        echo ""
        continue
    fi

    # Run the management command on the server
    ssh -o BatchMode=yes -o StrictHostKeyChecking=no django@"$IP" \
        "cd $REPO_DIR/backend && $MANAGE parse_existing_license_copies $CMD_ARGS 2>&1" \
    && echo "  ✓ Done — $LABEL" \
    || echo "  ✗ Command exited with error on $LABEL"

    echo ""
done

echo "═══════════════════════════════════════════════════════════"
echo "  All servers processed."
echo "═══════════════════════════════════════════════════════════"
echo ""
