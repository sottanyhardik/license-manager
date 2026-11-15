---
description: Run the CI-equivalent quality gates locally and report results honestly
argument-hint: "[frontend|backend|mds|mds-client|all]"
---
Run `sh scripts/dev/quality-gate.sh ${ARGUMENTS:-all}` (it mirrors `.github/workflows/ci.yml`).
Report a table: gate · PASS / FAIL / NOT RUN (with reason). For each FAIL, show the key failing lines
and the likely owner (agent). Exit 3 means some gates could not run — never describe that as passing.
