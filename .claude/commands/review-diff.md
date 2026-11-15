---
description: Independent parallel review of the working diff (correctness, language, security, performance, domain)
---
Collect `git diff` + `git diff --cached` file list. Then launch in ONE message, in parallel, read-only:
- `code-reviewer` (always)
- `django-reviewer` and `python-reviewer` if any `*.py` changed
- `typescript-reviewer` and `react-reviewer` if any `frontend/src/**/*.ts(x)` changed
- `security-auditor` if accounts/permissions/views/serializers/urls/settings changed
- `performance-engineer` if querysets, services, materialized views or list pages changed
- `cif-balance-auditor` if business-rule paths changed (see `.claude/rules/business-rules.md`)
- `silent-failure-hunter` if exception handling changed
Merge the results, de-duplicate, rank blocking → non-blocking, and give one verdict.
