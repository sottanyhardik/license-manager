# Target enterprise architecture

Adopt tenant-aware modular monolith: React -> DRF -> explicit domain services -> PostgreSQL; Redis/Celery for durable jobs. Bounded contexts: tenancy, masters, licences/restrictions, allocation, BOE/trade/reconciliation, reporting, Option B accounting. Application-level tenant scoping first; RLS later as defence in depth. Preserve APIs through staged caller migrations and rollback/dual comparison.
