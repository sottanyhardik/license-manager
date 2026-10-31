# Scope and non-negotiable requirements

## In scope

Complete preservation/rebuild of approved licence, SION/DFIA, allotment, BOE, trade, document, reconciliation, reporting, administration, integration and background-job capabilities; controlled addition of accounting; data migration; recovery; security and test coverage.

## Out of scope until explicitly approved

- production modifications during audit;
- destructive data cleanup or history regeneration;
- framework replacement without compatibility evidence;
- external-SaaS or multi-tenant claims without company-isolation proof;
- statutory/tax-accounting interpretations without CA approval.

## Required preservation controls

- Existing behaviour is a reference, not automatically a correct specification.
- Each changed rule is classified as preserve, approved defect correction, approved redesign, removal, new, or unverified.
- Historical records, documents and audit references are mapped before new schema implementation.
- No cutover without isolated restore, migration rehearsals, reconciliation, workflow UAT and rollback/delta-recovery plan.
- No rule may silently differ between backend, frontend, report, PDF or Excel.

