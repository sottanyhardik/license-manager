---
description: Produce the standard final implementation report for the current task
---
Write the final report with these sections, using only facts verified in this session:
1. **Summary** — what was done, in 3–5 lines.
2. **Changes** — files created/modified, grouped by area.
3. **Business rules** — "BUSINESS-RULE CHANGE: …" or "No business-rule change", plus API contract / permission impact.
4. **Quality gates** — table from `scripts/dev/quality-gate.sh` (PASS / FAIL / NOT RUN + reason).
5. **Reviews** — reviewer → verdict → blocking findings and how they were resolved.
6. **Open issues / risks** — including anything escalated to the human.
7. **Next steps** — including the git commands the human may want to run (never run push/merge yourself).
