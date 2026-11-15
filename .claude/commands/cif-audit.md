---
description: Audit the current diff (or a named area) against the canonical CIF/balance rules
argument-hint: "[path or licence number — default: current git diff]"
---
Use the `cif-balance-auditor` agent (and `boe-reconciliation-auditor` / `invoice-auditor` if BOE or
trade/invoice files are involved) to audit: ${ARGUMENTS:-the current `git diff` and `git diff --cached`}.
Rules: `.claude/rules/business-rules.md`. Run the balance test files if Postgres is available.
Output: verdict, findings with file:line and numeric examples, tests run with real results, and
whether this is a BUSINESS-RULE CHANGE.
