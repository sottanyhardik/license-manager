# Prompt — New Feature

Copy, fill the blanks, and run. Loads the right context first so the change fits conventions.

---

**Feature**: <one-line description>
**Layer(s)**: <frontend | backend | both>
**Affected app/page**: <e.g. `apps/license` / `pages/Allotment`>

Before writing code:
1. Read `CLAUDE.md` §3 routing table.
2. Frontend → read `.claude/rules/{react,typescript,frontend-ui}.md` + `.claude/context/{architecture,api}.md`.
   Backend → read `.claude/rules/{backend,database,security}.md` + `.claude/context/{api,business-domain,database}.md`.
3. Grep for existing patterns to reuse: `MasterViewSet` subclass, `@/components/ui/*`,
   `@/services`, `@/types`. Cite the files you'll mirror.

Then:
- Reuse before building new. Extend `MasterViewSet`/`AuditModel` on the backend; reuse UI
  primitives on the frontend.
- Add validation in serializers (backend) and the form layer (frontend).
- Add tests (`.claude/templates/test.md`); a new endpoint needs an `@pytest.mark.api` test.
- Preserve business logic and authorization. Declare permissions on any new endpoint.

Definition of done:
- [ ] Templates used: `.claude/templates/{component,service,viewset,test}.md` as applicable.
- [ ] Quality gate green — frontend `lint`→`typecheck`→`build`; backend `pytest`.
- [ ] Docs updated if API/DB/architecture changed (`CLAUDE.md` §10).
- [ ] PR checklist passed: `.claude/checklists/pr.md` (+ `security.md` if auth/input touched).
