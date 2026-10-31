# Dependencies and release gates

`../11-roadmap/dependencies.mmd` remains the current dependency graph pending consolidation into this directory. The critical path is source index/deployment evidence -> company and rule decisions -> migration mapping -> operational ledger/restriction core -> BOE/trade/reconciliation -> dry migration -> accounting parallel close -> restore/UAT -> cutover.

Do not parallelise changes to shared ledger, rule-engine, accounting-posting or schema boundaries without an approved contract and named owner.

