---
description: Start a new feature using the .claude feature workflow
argument-hint: "<short feature description>"
---

Begin work on the feature described in `$ARGUMENTS` by following the repo's feature workflow.

1. Read `CLAUDE.md` §3 routing table to pick the rules/context for the affected layer(s).
2. Load `.claude/prompts/feature.md` and follow it: read the layer rules + context, grep for
   existing patterns to reuse (`MasterViewSet`, `@/components/ui/*`, `@/services`, `@/types`),
   and cite the files you'll mirror.
3. Use the matching templates (`.claude/templates/{component,service,viewset,test}.md`).
4. Before declaring done, run the quality gate and `.claude/checklists/pr.md`
   (+ `security.md` if auth/input was touched).

Do not write code until you've reported which rules/context/examples you loaded and the
existing patterns you'll reuse.
