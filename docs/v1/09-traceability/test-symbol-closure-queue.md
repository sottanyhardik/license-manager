# Test-symbol closure queue

This queue turns the 509-row static test-symbol denominator into auditable
mapping batches. It is a planning register, not test coverage evidence. The
symbol index records test classes/symbols, not individual parametrized cases,
assertions, fixtures, browser specs, or proof that a test ran in the current
environment.

## Current denominator and classification method

**Verified by static register:** `test-symbol-register.tsv` contains 509
unique indexed test symbols, each currently `Partial` with `maps_to = To
reconcile`. The batch counts below were calculated from the current file path;
they are reproducible with an `awk -F '\t'` grouping of column 4. This is a
triage classification, not a source-behavior claim.

| Batch | Indexed test symbols | Basis / first mapping target | Priority |
| --- | ---: | --- | --- |
| Licence domain | 252 | Licence, balance, planning, SION, ledger and report `API-*`/`WF-*`/`BAC-*`/`SPC-*` records | P0/P1 |
| Core, sync and security | 109 | Auth/media, master/sync, activity, shared validation and operational `API-*`/`SCP-*`/`SYNC-*` records | P0/P1 |
| Other test modules | 61 | MDS-client, MDS or non-primary app/module evidence; establish owner/environment before mapping | P1/P2 |
| Root/API suite | 38 | Canonical API, authorization, integration and URL behavior | P0/P1 |
| Allotment | 15 | Allocation/lifecycle/availability `API-003–017`, `WF-05`, `BAC-*` | P0 |
| Reconciliation | 15 | `API-278–291`, `WF-08`, `RCF-*` | P0/P1 |
| Trade | 9 | `API-333–350`, capability documents, `WF-07` | P1 |
| BOE | 6 | `API-035–049`, hide/restore/parser evidence, `WF-06` | P0/P1 |
| Accounts | 3 | Authentication/user/admin command paths, `WF-01`/`WF-14` | P1 |
| Tasks | 1 | Task state transition/public task operations, `WF-12` | P1 |
| **Total** | **509** | Stable test-symbol denominator | — |

### Exclusions that need a separate relationship type

Twenty-four symbols have a fixture/helper-style filename (`factories`,
`assertions`, `helpers`, `utils`, or `conftest`); 485 do not. That filename
classification is only a review aid: a helper may encode a critical assertion,
and a test class may provide no relevant proof for a particular requirement.

Use one of these relationship values instead of claiming all indexed symbols
are behavior tests:

| Relationship | Meaning |
| --- | --- |
| `DIRECT_POSITIVE` | Named case proves one specified successful observable outcome. |
| `DIRECT_NEGATIVE_AUTH` | Named case proves anonymous/wrong-role/approved object-scope outcome. |
| `DIRECT_ERROR_RECOVERY` | Named case proves validation, rollback, retry or operator recovery outcome. |
| `SUPPORT_FIXTURE` | Factory/helper/assertion utility enables a test but is not itself proof. |
| `RELATED_ONLY` | Same domain but no specified API/route/requirement assertion. |
| `UNMAPPED` | Not yet reviewed. |

## Mapping workflow

For each test symbol, add a mapping record to the applicable API/route/workflow
contract rather than changing status from filename or test-module membership.

1. Locate the indexed class/symbol with `.claude/index/symbols.tsv`; read the
   smallest test/source scope necessary to establish its setup, endpoint or
   service call, and assertion.
2. Assign one primary `WF-*` and any exact `API-*`, `UI-*`, function/entity or
   decision IDs. A single test can have multiple mappings, but each mapping
   must name the assertion it contributes.
3. Record relationship type, input fixture/boundary, observed response/data
   effect, role/object context, run command/environment, and known missing
   recovery or browser evidence.
4. Link the precise test class/function back into the relevant operation/route
   register and [requirements-to-tests](requirements-to-tests.md). Do not
   treat source discovery as a passing test result.
5. Promote only a **requirement mapping**, never a whole test module, when
   the closure protocol's positive, authorization-negative and error/recovery
   evidence is complete.

## Ordered closure batches

| Order | Population | Why first | Exit evidence |
| --- | --- | --- | --- |
| Q1 | Root/API + Allotment + Reconciliation + BOE (74 symbols) | Direct P0 mutation, financial debit, correction and authorization paths | Every P0 operation has a named positive, direct role/object negative and error/recovery mapping or approved exclusion. |
| Q2 | Licence balance/planning/ledger subset of the 252 licence symbols | D2/D3-sensitive financial/entitlement outputs and async work | Golden Custom/Financial, restriction, replan, package/download mappings include labelled source/time and failure recovery. |
| Q3 | Core/sync/security (109) | D1/D4/D6, protected media, peer replay and master consistency | Auth/media/sync/audit mappings state exact owner policy dependency and controlled-environment requirement. |
| Q4 | Trade, account and task symbols (13) | Commercial correction, user administration and task lifecycle | D5-sensitive trade scope and user/task action matrices have direct API assertions. |
| Q5 | Other test modules (61) plus support/fixture relationships identified in every prior batch | Completes non-primary-module mapping and distinguishes support evidence | Each symbol is classified as direct/related/support/unmapped with evidence link and test-environment status. |

The five primary path batches sum to the 509-row denominator
(`74 + 252 + 109 + 13 + 61`). A symbol can still have more than one
requirement relationship; cross-domain mappings do not change that population.

## Known quality gaps to preserve

- The current suite results are recorded in [test and quality baseline](../01-discovery/test-and-quality-baseline.md); they do not prove every test
  symbol executed. The 2,708 licence/core run, 237 canonical run, 25 MDS run
  and 32 MDS-client run have materially different scopes.
- Frontend tests are not in this 509-symbol Python-index denominator. The 544
  frontend unit/component tests and 130 Playwright cases require their own
  mapping records.
- The browser baseline is failing (68 passed / 54 failed / 8 skipped). No
  Playwright discovery can satisfy a browser acceptance criterion until the
  harness, fixture and contrast failures are repaired and rerun.
- D1–D6 can determine the intended assertion. A current test showing
  role-wide multi-company access is evidence of current behavior, not an
  approved tenancy policy.

## Completion measure

Add these rows to the traceability coverage only when direct evidence is
entered:

| Measure | Current count | Closure target |
| --- | ---: | --- |
| Indexed test symbols with an exact requirement/API/route mapping | 0 / 509 | 509 / 509, each classified as direct, related, support or approved exclusion. |
| P0/P1 operations with positive + auth-negative + recovery test mapping | 0 / applicable operation population | Every selected P0/P1 operation, subject only to owner-approved policy limitations. |
| Browser route acceptance mappings | 0 / 57 | Every route requiring UI behavior, after a repaired deterministic harness. |

Until those targets are met, this document is a reproducible closure plan and
the test-symbol population remains **Partial**.
