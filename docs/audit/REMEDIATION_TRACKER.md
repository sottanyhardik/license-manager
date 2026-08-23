# License Manager remediation tracker

This tracker records the fresh-baseline remediation work.  It distinguishes a
production defect from a test that requires a schema/contract migration; a
passing focused test is never treated as full-suite verification.

| Test node / cluster | First traceback or evidence | Classification | Owner | Files changed | Focused verification | Full-suite verification | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Fresh backend baseline | `105 failed, 2412 passed, 45 skipped, 10 errors in 346.23s`; complete log: `/tmp/license-manager-pytest-baseline-XXXXXX.log` | Inventory | Release owner | — | Captured | Pending | In progress |
| Planning setup errors | Duplicate `ItemNameModel(name="WPC")`; missing `license_3411008090` and related percentage-usage fixtures | Fixture migration | Planning workstream | Scoped planning test fixtures only | Pending | Pending | In progress |
| Planning, SION, output-item execution, async replan | `test_output_item_auto_create`: a target-less STANDARD rule had no source group, so `OutputItemResolver` was unreachable; fixtures also had no live export-CIF entitlement. `test_sion_planning_rules` still expected `plan-sion` to calculate/persist in HTTP 200. `SionRuleResolver.has_percentage_cap_rules` and fixtures still used removed `output_item`. | Production defect plus invalid fixtures/stale HTTP expectation: source matching must not depend on a lazily-created canonical target; live financial balance remains an absolute cap; HTTP is queue-only; canonical rule target is `import_item`. | Planning workstream | `sion_planning_execution.py`; `sion_rule_resolver.py`; `test_output_item_auto_create.py`; `test_sion_generic_rule_engine.py`; `test_sion_planning_rules.py` | `DB_NAME=lm_planning_worker_20260820 … pytest apps/license/tests/test_output_item_auto_create.py -q --no-cov --tb=short`: 8 passed; schema/async modules await serialized run | Pending coordinator's serialized fresh baseline and final full run | Focused repair complete; stale async/schema assertions migrated |
| Pytest configuration warning | `PytestConfigWarning: Unknown config option: env` from `backend/pytest.ini`; `pytest-env` is not a declared test dependency and test-mode middleware already detects pytest from `sys.argv`. | First-party configuration defect | Planning workstream | `backend/pytest.ini` | Static configuration review; the next serialized pytest run must show no `PytestConfigWarning` | Pending final full run | Fixed: removed unsupported `env = TESTING=true` stanza rather than suppressing the warning or adding an unused plugin |
| Planning priority rerun | `/tmp/lm-planning-priority.log`: `19 failed, 40 passed, 1 warning in 17.16s`. Restored missing profile/action allocation-strategy bridge; its three focused API checks passed. Queue migration made SION redesign and basic percentage execution pass. | Remaining failures split between live-source fixture migration and stale contract expectations; one `UnorderedObjectListWarning` is a first-party pagination defect. | Planning workstream | `sion_planning_rule.py`; SION/percentage tests | Logged serial run | Pending | In progress |
| Retired bulk Auto Plan skips | Seven `plan-licenses` tests were skipped after endpoint consolidation. | Test-contract migration: each now exercises `/api/licenses/<id>/auto-plan/` with 202, durable request identity, no inline plan row, coalescing/default-mode/unknown-id behaviour; worker calculation remains covered by the durable replan worker integration suite. | Planning workstream | `test_auto_plan_license_api.py` | Awaiting serialized DB run | Pending | Replaced; no skip retained |
| Unordered plan pagination | DRF emitted `UnorderedObjectListWarning` when listing `LicenseItemPlan` records. | First-party production correctness defect | Planning workstream | `views/item_plan.py` | Awaiting serialized API test | Pending | Fixed deterministic queryset order (`pk`) |
| Authorization, IDOR, ledger, reports, pivots | 8 retired-route/contradictory IDOR assertions; 16 canonical pivot shape/merge failures; Excel/totals/live-balance/ledger clusters; report scope bypass found | Fixture migration plus production security repair | Authorization workstream | Scoped auth/ledger/report files only | Pending fresh nodes | Pending | In progress |
| Sync, collection/setup, warnings, skips, infrastructure | 4 sync failures; repeated missing-staticfiles `UserWarning`; 45 skips including retired allocation/MDS/table cases | Production/fixture decision pending | Sync/infrastructure workstream | Scoped sync/config files only | Pending fresh nodes | Pending | In progress |
| Frontend, typecheck, production build, browser workflows | Earlier 421 frontend tests passed; must be rerun after backend remediation | Verification | Release owner | Scoped frontend files only | Pending | Pending | Pending |

## Guardrails

- Backend database tests are serialized and use a unique `DB_NAME`; no normal
  development or production database is targeted.
- No test is deleted, skipped, xfailed, or weakened to conceal a failure.
- Automatic planning remains queue-only in HTTP handlers and signals.
- The full baseline log and the final full-suite log are retained under the
  system temporary directory for this audit run.
