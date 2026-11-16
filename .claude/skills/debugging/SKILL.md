---
name: debugging
description: Root-cause debugging method for backend/frontend bugs, failing tests and wrong numbers. Use for any bug or regression.
metadata:
  origin: project
---
Specialist: `debugging-specialist` (only for non-trivial bugs).

1. **Reproduce** with the smallest failing test/command; no repro → state what is missing.
2. **Locate**: Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges. Regressions: `git log -L :func:file`, `git blame`, `git log -S`.
3. **Isolate**: one hypothesis at a time, proven by evidence (test output, logs, local-DB read-only query).
4. **Fix** at the root cause, minimal; add a regression test that fails before / passes after.
5. **Verify**: targeted test → area gate. Wrong CIF/balance numbers → escalate per `.claude/rules/business-rules.md` before changing semantics.

**Output:** Root cause (file:line) · Evidence · Fix · Tests · Remaining.
