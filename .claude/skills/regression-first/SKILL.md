---
name: regression-first
description: Write a failing or characterization test before changing License Manager code, so behaviour changes are deliberate and visible — project layer over ECC tdd-workflow, django-tdd, python-testing and react-testing. Use at the start of every ERP implementation task, especially bug fixes and refactors of financial code.
metadata:
  origin: project
---

# regression-first

1. **Purpose** — every change is pinned by a test that fails before and passes after (or pins existing behaviour).
2. **Invocation criteria** — any implementation task; mandatory for balance/allotment/BOE/trade code and bug fixes.
3. **Required context** — ECC `tdd-workflow`, `django-tdd`, `python-testing`, `react-testing`; the task's
   acceptance criteria; approved decision rows for expected values.
4. **Workflow** — (a) bug fix: reproduce with a failing test first; (b) refactor: characterization test pinning
   current output on a synthetic fixture; (c) feature: test per acceptance criterion; (d) run it — confirm it
   fails for the right reason; (e) implement; (f) run targeted tests with the task's `TEST_DB_NAME`.
5. **Restrictions** — expected financial numbers come from approved rules or verified outputs, never invented;
   if the expectation depends on an open decision → `xfail(reason="blocked-on: OD-NN")` and report; never weaken
   or delete existing assertions without owner approval; synthetic fixtures only (no real customs data).
6. **Acceptance criteria** — hand-off shows the test failing before (or the pinned value) and passing after.
7. **Verification commands** — `cd backend && TEST_DB_NAME=<db> python -m pytest <node-id> -q`;
   `cd frontend && npx vitest run <file>`.
8. **Documentation references** — `.claude/skills/tdd-workflow/SKILL.md`, `.claude/skills/django-tdd/SKILL.md`,
   `.claude/agents/erp-qa.md`.
