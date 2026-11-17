# Claude usage log — BOE ERP modernization

Figures are copied from workflow completion notifications (subagent tokens only;
main-session tokens and dollar cost are not visible to the agent — record `/cost`
output here when the owner runs it). No figure is estimated.

| # | Workstream | Models (as configured per agent) | Agents | Subagent tokens | Cost | Work completed | Test evidence |
|---|---|---|---|---:|---|---|---|
| 1 | Discovery (iteration 1) | Opus 5.5 (inherited) | 7 | 633,297 | n/a | 48 findings, 5-workstream plan | read-only |
| 2 | Iteration 1 implementation + reviews | Opus 5.5 (inherited) | 9 | 715,893 | n/a | WS1–WS6, 3 reviews; commit `3ece31f0` | FE 807/807, BE 3152 passed / 1 pre-existing xfail, Playwright 29/29 (mocked) |
| 3 | Iteration 2 Phase A | A1–A5 + reviewers: Opus; F1, F2: Sonnet | 9 | 832,907 | n/a | Owner decisions D1–D15 implemented (uncommitted); reviews approve_with_fixes | per-agent targeted runs |
| 4 | Phase A completion (fixes + re-review) | Fixers: Sonnet; CIF review: Opus; security review: Sonnet | 5 | 281,295 | n/a | Review fixes; landed as `f202cedb` | BE gate 3339 passed / 1 pre-existing xfail; FE 814/814 + typecheck + lint + build; Playwright 29/29 (mocked); 1044 local BOEs echo-validated read-only (0 false 400s) |
| 5 | Phase B (B1–B4 + reviews + docs) | B1–B4: Sonnet; B3 review: Opus; code review: Sonnet; docs: Haiku | 7 | 401,513 | n/a | Detail route on ModuleWorkspace, sticky BOE form + unsaved guard, `save_boe_with_rows` (baseline 4→0), exporter service + golden tests | Focused per workstream; final: FE 835/835 + typecheck + lint + build; Playwright 26/26 (mocked); BE gate — see progress doc |

## Routing policy (owner, 2026-11-17, ~$500/month target)

Opus: architecture, canonical balance/merge/frozen-row logic, security architecture,
independent financial review, final acceptance. Sonnet: Django/React implementation,
service migrations, tests, routine reviews. Haiku/economical: docs, summaries,
inventories, mechanical edits. The main orchestrating session runs Opus 5.5 and cannot
switch its own model.
