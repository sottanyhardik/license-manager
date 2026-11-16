# Ad-hoc scripts (archived 2026-11-16)

One-off verification/trace/debug scripts moved from the repo root (`root/`) and `backend/` root
(`backend/`). They are **not** part of the test suite or CI and nothing imports them.

- Run backend ones from `backend/` with Django on the path, against the **local** DB only:
  `cd backend && PYTHONPATH=. DJANGO_SETTINGS_MODULE=lmanagement.settings .venv/bin/python ../scripts/adhoc/backend/<script>.py`
- Never point them at staging/production (`.claude/rules/backend.md`).
