# Local browser and accessibility baseline

## Current result (after the 2026-10-31 repair pass)

**Verified by test on 2026-10-31.** `npx playwright test` (full suite, 130 discovered): **121 passed, 1 failed, 8 skipped, exit 1, 3.3 min**. Before the repair pass the same suite gave 68 / 54 / 8.

| Area | Before | After | What changed |
| --- | ---: | ---: | --- |
| `responsive.spec.ts` | 50 harness `TypeError`s, 1 timeout | **106 passed** | Loop variable shadowed the `page` fixture, so `page.path` was `undefined`; hard-coded port `5175` (the config uses `41731`) replaced by `baseURL`. Dashboard mobile test now seeds the same `localStorage` auth keys the app reads and mocks `/api/*`, and selects the semantic `<main>` instead of `[role="main"]`. |
| `trades.accessibility.spec.ts` and `trades.performance.spec.ts` | 2 serious axe failures | **5 passed** (both files) | Contrast: the route-scoped rule targeted `.page-actions`, which is never rendered by `MasterList`. It now matches the link by `href="/trades/create"`. Link name: 5 icon-plus-label spans in `MasterList.tsx` changed to `sr-only sm:not-sr-only`. |
| `item-pivot.sticky.spec.ts` | 1 timeout | **1 failed (unchanged)** | Waits for the seeded "E2E2509 Managed browser gate" control. The test is not guarded behind the isolated seeded harness and uses fallback credentials. Not hidden, not skipped. Fix needs a guarded seeded fixture. |

Interpretation: 53 of the 54 earlier failures are resolved by source or test-harness repairs verified by re-run. The remaining failure is a fixture precondition, not a layout or contrast measurement. Visual screenshot assertions are still only smoke checks: the responsive spec writes screenshots but does not compare them to approved snapshots.

Artifacts: Playwright clears and rewrites `frontend/test-results/` and `frontend/playwright-report/` on each run (both git-ignored). The responsive spec writes into `frontend/responsive-screenshots/`, which is **not** git-ignored. A recommendation to ignore it is in the execution log.

## Previous measured result (before repair — superseded)

**Verified by test on 2026-10-31.** `frontend npm run test:e2e` ran the local-only Playwright configuration. It starts Vite on `127.0.0.1:41731` and the configuration explicitly states that it never targets a production host.

| Measure | Result |
| --- | --- |
| Discovered Playwright cases | 130 |
| Passed | 68 |
| Failed | 54 |
| Skipped | 8 |
| Elapsed | 3.6 minutes |
| Overall status | Failed — do not present browser/a11y gate as green |

## Failure disposition

| Count | Evidence | Classification | V1 action |
| ---: | --- | --- | --- |
| 50 | Responsive screenshot cases across all configured viewport/page combinations throw `TypeError: Cannot read properties of undefined (reading 'replace')` at `frontend/e2e/responsive.spec.ts:82`, where `page.path` is used. | **Verified test-harness defect**, not visual regression evidence. The matching no-horizontal-overflow assertions passed for the affected screens. | P1: repair the test’s page metadata/path variable, then rerun screenshot assertions. Do not approve or update snapshots merely to hide the defect. |
| 1 | Item Pivot sticky test timed out waiting for the “E2E2509 Managed browser gate” control (`e2e/item-pivot.sticky.spec.ts`). | **Verified missing/unsatisfied local fixture or UI-contract assumption.** It is not proof that production Item Pivot sticky behavior is broken. | P1: document/seed the intended local browser fixture and assert the gate’s prerequisite rather than waiting for a non-existent control. |
| 1 | Mobile Dashboard filter-section responsive test timed out (`e2e/responsive.spec.ts:92`) waiting for `[role="main"]`. The test hard-codes port 5175 although Playwright uses 41731, and it suppresses navigation errors. | **Verified harness/isolation defect**, not a Dashboard layout conclusion. | P1: navigate through configured base URL, stop swallowing navigation errors and assert page readiness before measuring layout. |
| 1 | Item Pivot sticky test timed out waiting for the seeded “E2E2509 Managed browser gate”. Unlike data-bearing suites it is not isolated-harness gated and uses fallback credentials. | **Verified unguarded fixture-precondition failure**, not sticky-layout evidence. | P1: guard it behind the isolated seeded harness; assert seeded data before geometry checks. |
| 2 | Trade accessibility/performance tests found the same serious axe `color-contrast` violation on an “Add New” label: foreground `#1a2332`, blue background `#155dfc`, contrast ratio 3.0 where 4.5 is required. | **Verified one distinct accessibility defect reproduced by two tests** under WCAG AA. | P1: change the semantic button foreground/background token pairing and add a focused axe regression test. |

The 8 skipped data-bearing/download cases are not green evidence. Their fixture/backend prerequisites must be documented and exercised in a controlled environment before they count toward workflow acceptance.

## Positive evidence retained

The same run passed local login visual/a11y checks, authenticated-shell mobile navigation checks, many responsive no-overflow checks across Desktop/Tablet/Mobile viewports, selected licence-overview accessibility checks, and multiple trade error/empty/disclosure interactions. Passing local mocked cases do not prove direct API authorization, production data correctness, export/download authorization, or all route workflows.

## CI gate recommendation

Split the browser job into deterministic strata rather than a single opaque `test:e2e` gate:

1. local unseeded accessibility/responsive smoke, with the harness defect repaired;
2. seeded data-bearing workflow/browser tests against disposable backend/database services;
3. file/export/download tests with controlled object storage; and
4. explicitly labelled visual-snapshot tests with stable font/browser baseline.

Each P0/P1 route in the [route/API contract register](../09-traceability/p0-p1-route-api-contract-register.md) needs a suitable stratum plus API negative/error coverage. The current result proves that E2E assets exist and exercise meaningful states, but it does not close that acceptance gate.

The exact root-cause counts, source evidence and repair acceptance criteria are in [E2E failure analysis](e2e-failure-analysis.md).
