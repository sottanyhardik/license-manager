---
name: test-driven-development
description: Project TDD loop with the exact test commands for backend and frontend. Use when building a feature or fixing a bug test-first.
metadata:
  origin: project
---
Generic: ECC `tdd-workflow`, `django-tdd`, `python-testing`, `react-testing`. (ECC's fixed 80%-coverage rule is not adopted here — cover the changed behaviour.)

1. **Red**: write the failing test next to existing ones (`backend/tests/…`, `backend/apps/<app>/tests/…`, `frontend/src/**/*.test.tsx`). Run it and see it fail for the right reason.
   - Backend: `cd backend && python -m pytest <path>::<test> -p no:cacheprovider` (app tests add `--import-mode=importlib`).
   - Frontend: `cd frontend && npx vitest run <file>`.
2. **Green**: smallest change that passes. 3. **Refactor** with tests green.
4. Risky change to untested code → characterization test first.
5. Money/CIF assertions use `Decimal('…')`, never floats.
6. Finish with skill `regression-testing`.
