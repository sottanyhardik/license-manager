# Backend-symbol closure queue

**Inferred from static discovery; proposed for V1 audit execution.** This
queue makes the 8,046-symbol denominator tractable without claiming that a
static symbol is callable, reachable, business-critical, or behaviorally
mapped. The authoritative per-symbol status remains `Partial` in
[backend-symbol-register.tsv](backend-symbol-register.tsv).

## Measured partition

The figures below were calculated from the current TSV rows (`NR > 1`) by
`module_or_file` path. Categories are deterministic path buckets, applied in
the displayed order; they are a work-planning partition, not a language AST
classification. The buckets sum to **8,046**.

| Static path class | Symbols | Treatment in the closure program |
| --- | ---: | --- |
| Test modules | 4,092 | Map tests to a requirement/API/route only when a direct assertion can be evidenced; do not force all helpers into business-function review. |
| Shared/core-model paths | 437 | Review by model/constraint/signal/migration boundary, starting with records on P0/P1 workflows. |
| Service paths | 890 | First production-code queue: review transactions, callers, outputs, errors and authorization context. |
| View paths | 460 | Reconcile each callback/action with API registration, serializer/queryset, permission and consumers. |
| Serializer paths | 300 | Reconcile inherited and dynamic fields/writes with API DTOs and model effects. |
| Management command paths | 418 | Use command flags, dry-run, write, backup/recovery and operator-control contracts. |
| Migration paths | 222 | Review by migration graph/affected data/backfill/recovery, not as independent runtime functions. |
| Signal paths | 49 | Reconcile registration, trigger order, transaction/on-commit behavior and repeat delivery. |
| Task paths | 40 | Reconcile broker, identity, retry/idempotency, state and operator recovery. |
| Script paths | 96 | Classify as supported operation, one-off forensic aid, test helper or candidate retirement; preserve before removal. |
| Vendor paths | 142 | Exclude from application behavior mapping unless a local patch/configuration makes it an owned runtime dependency; retain dependency/security inventory. |
| Other application/support paths | 900 | Triage into settings/URLs/forms/filters/helpers/admin/templates/utilities before deeper review. |

The indexed symbol kinds are also measured: 4,133 methods, 2,606 functions,
525 classes, 145 models, 96 routes, 52 views, 41 serializers and 448 static
test symbols. These kind counts are index output, not a claim about Python
runtime reachability.

## Domain batches

These are **ownership batches**, not an additional disjoint partition: a
licence-domain test or migration appears in both its owning-domain batch and
the cross-cutting B9 review lane. The figures therefore must not be summed.

| Batch | Static population | Initial priority rationale | Required evidence before a symbol can leave `Partial` |
| --- | ---: | --- | --- |
| B1 Licence | 4,435 | Largest ownership domain; balances, planning, ledger and report paths are financially consequential. | Tie each reviewed symbol to balance/planning/ledger contracts, callers, engine/provenance, state effect and focused tests. |
| B2 Core | 1,879 | Cross-domain models, generic CRUD, sync, media, filters, exports, settings and commands amplify defects. | Resolve dynamic registration, shared serializer/view behavior, MDS/sync/command effects and authorization context. |
| B3 Allotment | 360 | Allocation capacity and release write entitlement-critical records. | Locking, plan identity, debit basis, replan, role/object tests and failure recovery. |
| B4 Trade | 244 | Commercial evidence, invoices/documents and balance inputs. | Transaction/reversal, document capability, financial engine consumers and D5 limitations. |
| B5 Reconciliation | 192 | Immutable allocation/reversal/merge paths have high financial integrity risk. | Independent consumption tracks, locks/history, error/retry and D1/D2/D5/D6 policy gates. |
| B6 BOE | 162 | Import evidence, parser, hidden/correction and downstream balance effects. | File lifecycle, correction/hide/restore idempotency, recalculation and role/object matrix. |
| B7 Accounts | 150 | Authentication and permissions protect every application domain. | Anonymous/wrong-role/object scope, token/session/revocation and D1/D4 policy. |
| B8 Tasks and non-app support | 588 | Includes task app, project settings/URLs, shared, scripts, root tests and setup. | Startup/configuration, operator access, external integration, deployment and recovery characterization. |
| B9 Tests/migrations/vendor | 4,456 | Large but not first business-behavior review population. | Requirement linkage, historical data effect/rollback, dependency ownership or explicit exclusion. |

B8 is the raw non-`apps/*`/support population. B9 is an intentionally
overlapping lifecycle category spanning every domain. The queue is for
scheduling only; no row in the machine register is relabelled by this
document.

## Closure order and parallel lanes

1. **P0 mutation lane:** B1 balance/replan, B3 allocation, B5 reconciliation,
   B6 correction/hide/restore, B7 authorization and B2 protected media. This
   lane is blocked from policy-changing implementation by D1–D3, but direct
   characterization can proceed.
2. **P1 durable-work lane:** B1 ledger/package, B2 sync/MDS, B8 background
   configuration and B4/B6 document pipelines. It needs broker/storage/peer
   recovery evidence.
3. **P1 generated-CRUD lane:** B2 shared views/serializers/filters and all
   domain subclasses. One inherited behavior record may support several
   endpoints, but it cannot replace action-level contract evidence.
4. **Data lane:** B9 migrations plus model symbols in B1–B6. Reconcile with a
   scoped database and backup/restore drill before schema work.
5. **Residual lane:** tests, scripts, admin/helpers and vendor are triaged only
   after their callers' domain boundary is known. A symbol may be classified
   as historical/support-only with evidence; it is not silently deleted.

These lanes can run in parallel when they do not change shared evidence rows.
They must merge through the common [contract-closure protocol](contract-closure-protocol.md).

## Per-symbol review card

For each scheduled batch, copy the stable `BE-*` identity and fill only
evidence that was directly observed:

```text
BE-ID / symbol / source line:
Static classification and owning domain:
Reachability/caller evidence (direct, static-only, dynamic registration, or unknown):
Inputs/output/side effects and transaction boundary:
Authorization or execution identity:
Data/schema/file/background dependencies:
Named tests and exact assertion scope:
Failure/retry/concurrency/rollback behavior:
Related API/UI/workflow/decision IDs:
Recommended classification and priority:
Audit status (Verified / Partial / Unverified) and evidence label:
```

## Important limitations

- The existing `priority` column contains **5,543 P1** and **2,503 P2** rows
  and no P0 rows. It is a broad static triage field, not the approved V1
  prioritization source; use the P0/P1 workflow, risk and decision registers
  for implementation sequencing.
- Static imports/dependents are a navigation aid, not a function call graph.
- Django signals, DRF inheritance, Celery registration, management-command
  discovery and dynamic serializers require runtime/source reconciliation.
- This queue does not authorize refactoring, removal or a status promotion.
