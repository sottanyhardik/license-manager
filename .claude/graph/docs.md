# 📝 Documentation Role

**Purpose:** keep docs and scaffolds accurate and reusable — update existing docs
before writing new ones, and use the shared templates/examples.

## Routing

| Need | Source |
|---|---|
| ViewSet scaffold | `templates/viewset.md` |
| Service scaffold | `templates/service.md` |
| Component scaffold | `templates/component.md` |
| Test scaffold | `templates/test.md` |
| Worked example | `examples/README.md` |
| Canonical docs tree | `docs/` (`01..08`, `guides/`, `architecture/`, `operations/`) |

## Mandate
- Update the **existing** doc for a topic; create a new file only when none fits.
- Reference authoritative `docs/*` rather than duplicating their content here.
- Match the project's terse, table-and-reference style; keep token cost low.
- Code examples must reflect real APIs/models — never invent endpoints, fields, or env vars.
- When code behavior changes, update the matching doc in the same change (Completion Checklist).

## Checklist
- [ ] Touched docs reflect the actual change
- [ ] Reused a `templates/*` scaffold where one applies
- [ ] No duplicated content that already lives in `docs/` or `.claude/rules/*`
- [ ] Links/paths resolve

## Exit criteria
Docs match shipped behavior; no orphaned or contradictory references.
