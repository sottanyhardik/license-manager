# API register consistency validation

**Validation date:** 2026-10-31. This is a documentation-integrity check of
the V1 OpenAPI operation register and the three source-contract registers. It
does not test the deployed API, validate a DTO, or promote a contract from
`Partial`.

## Method

The check used the stable `API-###` ID, method and path columns in
[`api-operation-register.tsv`](api-operation-register.tsv), then compared the
declared disjoint ranges in the three source-contract registers. The generated
operation table was checked for duplicate stable IDs and blank method/path/
operation-ID fields. The licence and remaining registers also contain one
appendix row per operation; their normalized method/path strings were joined to
the TSV by stable ID.

The identity/master register intentionally groups generated seven-operation
master families in range rows. It therefore cannot be mechanically checked as
one Markdown row per operation. Its declared range partition, rather than a
regex count of visible `API-###` strings, is the appropriate evidence for
that register.

## Results

| Check | Actual result | Status | Meaning |
| --- | ---: | --- | --- |
| Stable IDs in operation TSV | 354 rows; 354 unique `API-###` IDs | Verified | No duplicate ID or malformed stable ID found. |
| Required operation-table identity fields | 354/354 method, path and operation-ID values present | Verified | This is metadata completeness, not response-contract completeness. |
| Source-contract partition | 142 identity/master + 113 licence/allotment/BOE/planning/ledger + 99 remaining = 354 | Verified | The declared range populations sum to the OpenAPI denominator. |
| Partition overlap | 0 IDs | Verified | No `API-###` identity is assigned to two source-contract populations. |
| Partition vs operation TSV | 0 missing, 0 unexpected IDs | Verified | The range partition exactly covers API-001 through API-354 currently present in the operation TSV. |
| Licence appendix method/path comparison | 113/113 joined; 0 normalized mismatches | Verified | Markdown method/path metadata agrees with the operation TSV. |
| Remaining appendix method/path comparison | 99/99 joined; 0 normalized mismatches | Verified | Markdown method/path metadata agrees with the operation TSV. |
| Identity/master grouped-range method/path comparison | Not individually machine-comparable | Partial by design | Master router families are represented as ranges; individual method/path values remain in the TSV. |

## Declared partition used for the check

| Register | Exact IDs / ranges | Count |
| --- | --- | ---: |
| [Identity, masters, sync and operations](api-operation-contracts-auth-masters.md) | 018–034, 163–171, 172–248, 249–253, 254–267, 268–269, 315–320, 321–332 | 142 |
| [Licence, allotment, BOE, planning and ledger](api-operation-contracts-license.md) | 003–017, 035–049, 068–074, 080–091, 092–118, 119–127, 128–155 | 113 |
| [Remaining operations](api-operation-contracts-remaining.md) | 001–002, 050–067, 075–079, 156–162, 270–314, 333–354 | 99 |

The ranges are disjoint and exhaust the 354 registered IDs. The apparent
result of a simple `API-###` text search (264 unique literal IDs) is not a
gap: the identity/master register deliberately records generated CRUD families
as compact ranges such as `API-172–178` rather than expanding each member
into prose.

## Non-claims and next validation

This check proves that the current planning artefacts identify the same
registered operation population. It does **not** prove request/response
fixtures, action-level permission or object/company scope, consumer behavior,
data effects, error recovery, OpenAPI warnings, or focused test coverage. The
complete individual-operation contract measure therefore remains **0/354** in
[traceability coverage](traceability-coverage.md).

When a grouped identity/master family is expanded into complete operation
contracts, retain the current `API-###` key and add a per-operation
method/path/serializer/authorization/consumer/test row. Re-run this validation
after any OpenAPI regeneration, router change, or operation-register rewrite.
