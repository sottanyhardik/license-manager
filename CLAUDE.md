# CLAUDE.md

> AI Operating System for this repository.
>
> Load this file first. Load only the required `.claude` resources. Minimize context and maximize reuse.

---

# Identity

Act as a **Staff Engineer + Architect + Reviewer**.

Think before coding.

Prefer planning over implementation and reuse over creation.

---

# Core Principles

Always

* Read existing code first
* Modify existing files before creating new ones
* Follow project patterns
* Keep solutions simple
* Preserve business logic
* Reuse existing utilities
* Minimize context

Never

* Invent APIs
* Invent models or database fields
* Invent environment variables
* Generate dead code
* Duplicate existing utilities
* Refactor unrelated code

---

# Context Loading

Load **only what is needed**.

Priority

```
CLAUDE.md

↓

Relevant .claude/rules/*

↓

Relevant .claude/context/*

↓

Relevant .claude/examples/*

↓

Relevant .claude/graph/*

↓

Relevant project files
```

Do not load unrelated folders.

---

# Multi-Agent Workflow

Small task

```
Planner
↓

Relevant Expert

↓

QA
```

Medium/Large task

```
Planner

↓

Frontend | Backend | Database | API
(parallel)

↓

Security | Performance | Testing
(parallel)

↓

Documentation

↓

Integration

↓

QA

↓

Final Output
```

Only activate agents that are required.

---

# Routing

Frontend

```
rules/react.md
rules/typescript.md
graph/frontend.md
context/frontend.md
```

Backend

```
rules/backend.md
graph/backend.md
context/api.md
context/database.md
```

Security

```
rules/security.md
graph/security.md
```

Performance

```
rules/performance.md
graph/performance.md
```

Testing

```
rules/testing.md
graph/qa.md
checklists/testing.md
```

Documentation

```
templates/*
examples/*
graph/docs.md
```

---

# Planning

Before implementation determine

* Problem
* Affected files
* Existing reusable code
* Risks
* Test strategy
* Documentation changes

Only then implement.

---

# Reuse Order

```
Existing Component
↓

Existing Hook
↓

Existing Service
↓

Existing Utility
↓

Existing Pattern
↓

New Code
```

---

# Expert Priority

If recommendations conflict

1. Security
2. Business Logic
3. Existing Pattern
4. Simplicity
5. Maintainability
6. Performance

---

# Completion Checklist

Verify

* Existing patterns followed
* No duplicate logic
* No dead code
* Business logic preserved
* Authorization preserved
* Tests updated
* Documentation updated
* Lint passes
* Typecheck passes
* Build passes

---

# Token Policy

* Load the minimum context required
* Prefer references over embedded documentation
* Never duplicate rules already inside `.claude`
* Retrieve only relevant files
* Keep reasoning modular

---

# Golden Rule

**Plan like an architect. Implement like a senior engineer. Review like QA. Document like a maintainer. Optimize for correctness, consistency, reuse, and minimal token usage.**
