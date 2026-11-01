# State machines

Allocation release/reactivation, planning/replan and ledger-package retry/finalization/cleanup/recovery are implemented stateful paths. V1 must extract explicit transition tables, permitted actors, idempotency and compensation from source/tests before changing them. This document deliberately does not invent transitions.
