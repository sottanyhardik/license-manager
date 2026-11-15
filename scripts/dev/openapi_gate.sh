#!/bin/sh
# OpenAPI gate: generate + validate the drf-spectacular schema (run from backend/).
# Errors always fail. Warnings are ratcheted: the count may not exceed OPENAPI_MAX_WARNINGS
# (baseline 22 warnings / 6 unique at OD-09 adoption; lower as warnings are fixed, then
# switch to --fail-on-warn).
# Usage: openapi_gate.sh <python>
PY=${1:-python}
MAX=${OPENAPI_MAX_WARNINGS:-22}
OUT=$(mktemp)
"$PY" manage.py spectacular --validate --file "${OPENAPI_OUT:-/tmp/openapi-schema.yml}" >"$OUT" 2>&1
rc=$?
cat "$OUT"
n=$(sed -n 's/^Warnings: *\([0-9][0-9]*\).*/\1/p' "$OUT" | head -1)
rm -f "$OUT"
[ $rc -ne 0 ] && { echo "OpenAPI gate: schema generation/validation FAILED (rc=$rc)"; exit 1; }
[ -z "$n" ] && { echo "OpenAPI gate: could not read warning count"; exit 1; }
[ "$n" -gt "$MAX" ] && { echo "OpenAPI gate: $n warnings > allowed $MAX"; exit 1; }
echo "OpenAPI gate: OK ($n warnings, allowed $MAX)"
