# V1 documentation consistency audit

**Scope:** documentation-only integrity validation performed on 2026-10-31.
This audit checks the V1 documentation layer; it does not validate application
behavior, external URLs, an environment, or source-code claims beyond the
already recorded evidence. A passing internal-link or register check is not a
functional completion claim.

## Checks and results

| Check | Method and evidence | Result | Interpretation |
| --- | --- | --- | --- |
| Required V1 documentation structure | Enumerated `docs/v1/` against the requested 00–09 directory/document structure. The nine required sections contain 5, 8, 5, 6, 6, 7, 6, 7, 6 and 33 files respectively; the root README, execution log and legacy registers are present. | **Pass** | All requested core document paths are present. Additional deep-trace documents do not replace the required files. |
| Markdown local-link targets | Parsed inline Markdown links from every V1 Markdown file. HTTP(S), mail, data and fragment-only links were deliberately excluded because this is an offline path check. The check was rerun after DOC-01 using a local path resolver. | **Pass** | No unresolved local inline Markdown target was reported after the correction. |
| Core generated-register sizes | Counted rows excluding headers in current TSVs. | **Pass** | API operation register: 354; frontend route register: 57; backend symbol register: 8,046; test-symbol register: 509; legacy Markdown register: 645. These match their stated denominators. |
| Stable register identifiers | Checked API and UI identifiers for format, uniqueness and count in the current registers. | **Pass** | API: 354 unique `API-NNN` identifiers, no malformed/duplicate IDs. Routes: 57 unique `UI-NNN` identifiers, no malformed/duplicate IDs. This verifies TSV identity integrity only, not that every operation/route is behaviorally complete. |
| Cross-document denominator language | Reviewed the status, completion, coverage, workflow/test, operation-contract and deliverable matrices for the principal denominators and E2E baseline. | **Pass with intentional limitations** | Documents consistently retain 354 API operations, 57 routes, 8,046 symbols, 509 indexed test symbols, 645 legacy Markdown paths, and 68 passed / 54 failed / 8 skipped browser cases. All complete-contract claims remain 0/354 API and 0/57 routes. |
| Evidence-label posture | Reviewed README, completion audit and bounded deep-contract documents. | **Pass with local notation** | The root labels are present. Several deep slices use locally defined abbreviations such as `C`, `T`, `S`, `P`, and `D`; these are defined in their own documents and do not claim a stronger global status. |

## Confirmed correction

| ID | Severity | Location | Finding | Safe correction | Verification |
| --- | --- | --- | --- | --- | --- |
| DOC-01 | P2 documentation navigation | `09-traceability/high-centrality-function-contracts.md`, final related-evidence link | The relative path traversed out of `docs/v1/` and did not resolve. | Corrected to `../00-executive-overview/decisions-required.md`. | Offline local-link resolver rerun: pass; no source, policy or behavior change involved. |

## Deliberate limitations, not defects

- External HTTP(S) links and anchors were not fetched or rendered.
- Register integrity does not prove runtime callback registration, source behavior,
  endpoint DTO accuracy, user authorization, browser interaction, or test
  coverage; those limits are already governed by the [completion audit](completion-audit.md).
- The audit does not treat missing live-schema, deployment, backup/restore,
  worker, peer-sync, or owner-decision evidence as documentation faults. They
  remain final V1 completion gates.
- A documentation plan can be internally consistent while still being a
  proposal. Proposed architecture, UX and implementation material remains
  labelled accordingly.

## Required follow-up

1. Re-run the consistency check after a documentation batch changes a
   denominator, status label, route/API register, or top-level link.
2. Keep [the deliverable evidence matrix](v1-deliverable-evidence-matrix.md)
   and [completion audit](completion-audit.md) aligned; neither may promote a
   population merely because its inventory or a bounded deep sample exists.
