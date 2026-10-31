# Backend code audit

Django/DRF apps: accounts, core, licence, allotment, BOE, trade, reconciliation, tasks. Service/locking foundations exist, but planning/balance/restriction logic spans several paths. Retain modular monolith; introduce explicit application-service interfaces and characterisation tests before migration.
