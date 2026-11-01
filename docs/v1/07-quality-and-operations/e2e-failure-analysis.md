# E2E failure root-cause analysis

## Evidence boundary

**Verified by test and source inspection on 2026-10-31.** The local Playwright command discovered 130 cases and completed with 68 passed, 54 failed and 8 skipped. This analysis classifies the 54 failed *assertions*, not 54 independent product defects. It does not change source or tests.

| Failed assertions | Root cause | Evidence | Classification | V1 disposition |
| ---: | --- | --- | --- | --- |
| 50 | Screenshot loop dereferences `page.path`, but Playwright's `Page` fixture has no `path` property. | `frontend/e2e/responsive.spec.ts:69-84`; every viewport/page screenshot error context reports the same `TypeError` at line 82. Five configured viewports × ten page descriptors account for exactly 50 cases. | **Verified deterministic harness defect.** No screenshot comparison or visual assertion runs. | P1. Use a distinct descriptor variable (for example `route`) and construct the artifact filename from its `path`; rerun all 50 screenshot cases before making any visual conclusion. |
| 1 | Mobile Dashboard layout test waits for `[role="main"]` after navigation to hard-coded `http://localhost:5175/dashboard`; the locator times out. | `responsive.spec.ts:92-100`; failure context shows `locator.boundingBox` waits 30s for `[role="main"]`. The Playwright config’s base URL is `127.0.0.1:41731`, while the file hard-codes port 5175 and suppresses navigation errors with `.catch(() => {})`. | **Verified harness/isolation defect.** The timeout does not prove a Dashboard layout defect. Earlier no-overflow cases can also be false positives when navigation fails or targets an unrelated pre-existing server. | P1. Use relative URLs/baseURL, do not suppress navigation failure, and establish authenticated/mock fixture readiness before measuring layout. Add an assertion that the expected route heading/main rendered. |
| 1 | Item Pivot sticky test logs in and expects a seeded “Managed browser gate” control, but the control is absent in the observed local state. | `item-pivot.sticky.spec.ts:3-13`; failure context waits 30s at line 10. The page snapshot rendered Item Pivot but not that named control. Unlike data-bearing/download suites, this test has no `LM_REAL_E2E` opt-in guard and uses fallback credentials. | **Verified unguarded fixture precondition failure.** It does not prove sticky layout behavior is broken because the test never reaches the sticky assertions. It also weakens the claim that every data-bearing test is isolated. | P1. Put it behind the same explicit isolated-seeded-harness guard, remove hard-coded credential fallback, seed/assert the fixture before selecting it, then run sticky geometry against that isolated dataset. |
| 2 | Same serious WCAG AA contrast defect is detected by two separate trade suites. | `trades.accessibility.spec.ts:73-98` and `trades.performance.spec.ts:90-110` invoke axe; both failure contexts identify `.bg-blue-600 > .sm\\:inline.hidden` for the “Add New” link, `#1a2332` on `#155dfc`, ratio 3.0 versus required 4.5. | **Verified one distinct UI accessibility defect, reproduced by two tests.** | P1. Correct semantic foreground/background token pairing; retain one focused axe assertion and rerun both suites at desktop and mobile widths. |

The counts reconcile exactly: `50 + 1 + 1 + 2 = 54` failed assertions.

## Skipped cases

The eight skips are intentional, but are **not green browser evidence**:

- five data-bearing workflow cases in `data-bearing.real.spec.ts`;
- one custom-ledger download case;
- one ledger-package download case; and
- one financial-ledger invoice download case.

Each is gated by `LM_REAL_E2E === "1"` and documentation states it requires a newly provisioned isolated database and seeded browser harness. This is a sound direction, but the runner that provisions it was not executed in this audit.

## Correctness implications

1. The passing 50 responsive overflow checks cannot be treated as route-level evidence until hard-coded port 5175 and swallowed navigation errors are removed. The test configuration otherwise provides base URL `127.0.0.1:41731` and Vite proxies `/api` to a configurable/local target.
2. The two axe failures prove a visual-accessibility defect; they do not establish whether other components share the token problem. A token/component audit is necessary after repair.
3. Data-bearing tests are appropriately opt-in, but Item Pivot sticky is an exception. It should be brought under the isolated-harness policy before it is allowed in CI.
4. Neither a passing mocked Playwright assertion nor the observed local page verifies server authorization, financial correctness, upload/download access control, or a production deployment.

## Repair acceptance sequence

| Task | Acceptance evidence | Priority |
| --- | --- | --- |
| Make responsive test navigation deterministic | All 50 screenshot tests reach an asserted page heading/main using Playwright base URL; no navigation exception is swallowed; artifacts are saved with descriptor path. | P1 |
| Restore isolated fixture discipline | Item Pivot sticky skips unless isolated harness is explicitly enabled; with it enabled, fixture seeding and gate selection are asserted before geometry checks. | P1 |
| Fix contrast | Axe reports no serious/critical contrast violation for the Add New link at desktop and mobile; token/component regression test added. | P1 |
| Execute seeded browser strata | All eight previously skipped data-bearing/download cases execute only against a disposable backend/database/storage setup and clean up after themselves. | P1 |
| Promote CI gate | Local mock and isolated seeded suites are separate CI jobs with deterministic browser/font/runtime versions, artifacts on failure and no production/default shared-service fallback. | P1 |

Until the first three tasks pass, `npm run test:e2e` remains a failing baseline and cannot be a release gate.
