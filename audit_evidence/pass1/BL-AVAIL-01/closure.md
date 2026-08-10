# BL-AVAIL-01 — Closure Record

## Title

`available_value_calculated` can use stale cached license balance.

## Status

**CLOSED — VERIFIED WITH FULL-SUITE VERIFICATION EXCEPTION**

## Severity

High (as established by the read-only investigation).

## Fix

`LicenseImportItemsModel.available_value_calculated` now reads the
authoritative live Financial Ledger balance through
`LicenseBalanceCalculator.calculate_financial_balance(self.license)`.

Bulk paths use the existing `available_value_bulk_map()` / batched Financial
Ledger calculation; no per-item live-calculation loop was introduced.

## Verification

- Focused BL-AVAIL-01: **25 passed / 0 failed / 0 skipped**.
- Affected regression suite: **84 passed / 0 failed / 0 skipped**.

The completed evidence covers stale-low and stale-high balances, open/AU and
percentage conditions, allocation validation in both directions, serializer
fallback, Ledger PDF, legacy Excel, bulk live-balance calculation, flat query
growth, and existing serial-1 semantics.

## Full-suite verification exception

The full backend suite is **UNVERIFIED**. No pass/fail count or delta is
available; none is inferred from partial output.

Three controlled attempts could not yield a recoverable pytest termination
summary:

1. The configured suite started, but the execution channel lost its final
   pytest summary.
2. A directly tracked pytest PID exited with an empty captured log and no
   recoverable pytest summary or exit code.
3. A foreground PTY disconnected while pytest was running. The real pytest
   process was confirmed alive and later exited, but its output and exit code
   were not recoverable.

This is an environmental verification limitation, not evidence of a product
test failure. A complete backend-suite result remains unavailable and is not
represented as green.

## Scope confirmation

- Production changes: BL-AVAIL-01 only.
- Schema migration: none.
- Git operations during implementation/verification: none.
- A3627: untouched.
- IncentiveLicense: untouched.
- BL-LEDGER-02: unchanged / CLOSED — VERIFIED.
