# Backend function catalog

The generated index exposes 8,046 backend symbols, 102 service files and 49 view files. It is a locator, not a complete caller catalogue. V1 classifies high-centrality functions first: balance calculator (57 dependents), canonical ledger service (34), role permissions (35), allocation services and durable job handlers.

## Static symbol coverage baseline

| App | Functions | Methods | Models | Views | Serializers | Indexed tests | Commands | Signals | Task files | Audit status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| accounts | 25 | 70 | 5 | 6 | 0 | 3 | 4 | 1 | 1 | Partial |
| allotment | 79 | 226 | 7 | 1 | 0 | 15 | 4 | 1 | 0 | Partial |
| bill_of_entry | 61 | 69 | 4 | 2 | 0 | 6 | 0 | 0 | 0 | Partial |
| core | 396 | 1,110 | 50 | 17 | 24 | 109 | 37 | 1 | 2 | Partial |
| license | 1,640 | 2,164 | 49 | 23 | 17 | 252 | 27 | 1 | 1 | Partial |
| reconciliation | 39 | 118 | 6 | 1 | 0 | 15 | 3 | 0 | 0 | Partial |
| tasks | 4 | 19 | 7 | 1 | 0 | 1 | 0 | 0 | 0 | Partial |
| trade | 69 | 122 | 17 | 2 | 0 | 9 | 2 | 0 | 0 | Partial |

Counts are **Verified by static index**; they are not a test-coverage claim. “Partial” means symbol discovered and assigned to its domain but caller, side-effect, authorization and test fields have not been completed per symbol. Dynamic registrations and inherited methods are explicit exclusions until resolver/source reconciliation.

The [per-symbol register](../09-traceability/backend-symbol-register.tsv) now enumerates all 8,046 indexed backend symbols with stable IDs and explicit Partial status. It includes static file-dependent counts for 3,136 symbols; this is import blast radius, not a true function caller graph. Its remaining `To reconcile` fields are the auditable backlog; index presence never implies functional verification.
