# Checklist — Testing

Rule: `.claude/rules/testing.md`. Config: `backend/pytest.ini`. Runner: `run-tests.sh`.

- [ ] New/changed business logic has a **unit** test (`@pytest.mark.unit`).
- [ ] New/changed endpoint has an **api** test (`@pytest.mark.api`) covering success + a 403/401 path.
- [ ] Bug fix has a **regression** test that failed before the fix.
- [ ] Edge cases covered: zero/negative/over-draw balance, `frozen` BOE row, partial allotment,
      expired/blacklisted JWT, unauthorized role.
- [ ] Tests use the right marker so suites slice cleanly (`unit/api/integration/database/slow`).
- [ ] Reused existing fixtures (`backend/tests/`, `conftest.py`) rather than redefining.
- [ ] Suite green: `./run-tests.sh --fast` (or full `./run-tests.sh` before release).
- [ ] Frontend gate green: `lint` → `typecheck` → `build` (no JS test runner configured).
