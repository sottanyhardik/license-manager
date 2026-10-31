# Workstreams and ownership

| Workstream | Scope | Dependencies | Reviewer / exit |
|---|---|---|---|
| A - audit/architecture | Inventory, route/API/workflow contracts, ADRs | Source index, access | Tech lead; evidence register complete |
| B - backend | Domain services, APIs, transactions, jobs | Approved contracts | Backend + domain review |
| C - frontend | Routes, forms, work queues, accessibility, API contracts | Stable APIs/workflow cards | UX + QA UAT |
| D - data/migration | Mapping, files, rehearsals, reconciliation, rollback | Isolated restore + decisions | DB architect + owner |
| E - licence/trade/domain | Ledger, SION, AU, caps, BOE/allocation rules | Official rule examples | Domain owner + QA |
| F - accounting | Policy, GL, subledgers, statements, bank | Stable operations + CA decision | CA + security |
| G - QA | Golden data, E2E, failures, regression, release evidence | All workstreams | QA lead |
| H - security/performance | Scope, security tests, profile/baseline | Architecture + staging | Security/performance reviewer |
| I - operations/release | CI, environments, backups, monitoring, cutover | Staging / restore | DevOps + release board |

