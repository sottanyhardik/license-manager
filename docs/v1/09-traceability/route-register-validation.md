# Route-register consistency validation

**Validation date:** 2026-10-31. This is a read-only documentation-register
check. It validates identifiers and stated grouping between V1 artifacts; it
does not validate the React router at runtime, API behavior, browser states,
or server authorization.

## Method and evidence boundary

The validation compared the stable `UI-*` identifiers in:

1. [frontend route register](frontend-route-register.tsv), the authoritative
   static denominator;
2. [frontend route workflow map](frontend-route-workflow-map.md);
3. [route-by-route redesign](../03-ui-ux/route-by-route-redesign.md), including
   its exact coverage index; and
4. [P0/P1 route-to-API register](p0-p1-route-api-contract-register.md).

Identifier extraction used `rg -o 'UI-[0-9]{3}' … | sort -u`; the two range
notations in the P0/P1 register were expanded manually for the count below:
`UI-001–004` represents four IDs and `UI-043–044` represents two IDs.

| Population / check | Expected | Result | Status |
| --- | ---: | ---: | --- |
| Distinct IDs in the TSV denominator | 57 | 57 (`UI-001`–`UI-057`) | Verified for static register identity |
| TSV IDs present in route workflow map | 57 | 57; no extras/missing | Verified for identifier coverage |
| TSV IDs present in redesign exact-coverage index | 57 | 57; no extras/missing | Verified for proposed-design coverage |
| P0/P1 route IDs represented after range expansion | 49 | 49 in 45 table rows | Verified for stated P0/P1 grouping |
| P0/P1 aliases | 4 SION aliases share one row; 2 ledger-detail aliases share one row | 49 IDs / 45 rows | Verified as intentional grouping |

## Priority-source discrepancy

The route-to-API document correctly identifies **49** P0/P1 route IDs and
eight excluded routes: `UI-014`, `UI-016`, `UI-036`, `UI-037`, `UI-046`,
`UI-049`, `UI-056`, and `UI-057`. (The apparent omission of `UI-002`–`004`
and `UI-044` from simple identifier extraction is only the range-notation
effect described above.)

However, every TSV record currently contains `P1` in its `priority` field.
That makes the TSV alone imply **57 P1** routes and cannot support the
P0/P1 register's 49-route selection. This is a **documentation-metadata
consistency gap**, not evidence that the route grouping or application is
wrong.

| Required reconciliation | Proposed owner / dependency | Acceptance evidence | Current status |
| --- | --- | --- | --- |
| Set each TSV route priority to the approved P0/P1/P2/P3 classification, or add an explicit separate `implementation_priority` field with a documented source. | Product/technical owner during M0/M1; no frontend behavior change. | Every UI ID has one priority source; P0/P1 selection in the route/API register is mechanically reproducible. | Partial |
| Preserve alias expansion rules in a machine-readable field or companion mapping. | Traceability owner, M1. | A 49-ID selection can be generated without interpreting Unicode ranges. | Partial |

Until that reconciliation, the P0/P1 register remains the authoritative
priority subset for implementation acceptance work because it explicitly
lists the selection and its grouped aliases. The TSV remains the authoritative
57-route discovery denominator, not the authoritative priority source.

## What this does not close

All 57 route records remain **Partial** for functional coverage. The check
does not add browser observations beyond the two already documented
read-only screens (`/login`, `/bill-of-entries`), and it does not prove any
loading/empty/success/error/denied state, API response, object/company scope,
or accessibility interaction. Those requirements remain governed by the
[closure protocol](contract-closure-protocol.md) and the [P0/P1 route/API
acceptance register](p0-p1-route-api-contract-register.md).
