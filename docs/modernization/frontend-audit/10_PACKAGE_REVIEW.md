# Package Review — four proposed frontend dependencies (AWAITING OWNER APPROVAL)

Date 2026-11-16. Status: **NOT APPROVED.**

**Disclosure.** These were already installed (pinned, `--save-exact`) into `frontend/package.json` and `package-lock.json` during the earlier autonomous phase, before the owner asked that no package be installed without approval. They are **uncommitted** and will **not** be committed unless approved. Lockfile delta: `+223 / −31` lines.

| Package | Version | License | Runtime deps | Audit | Installed size |
|---|---|---|---|---|---|
| `@tanstack/react-table` | 8.21.3 (stable v8; v9 deliberately not used) | MIT | `@tanstack/table-core` | no advisories | 0.8 MB + core 3.5 MB |
| `react-hook-form` | 7.91.0 | MIT | none | no advisories | 2.4 MB |
| `zod` | 4.6.7 | MIT | none | no advisories | 8.1 MB (tree-shaken in build) |
| `@hookform/resolvers` | 7.0.1 | MIT | `@standard-schema/utils` | no advisories | 2.2 MB |

Every version chosen is at least 2 weeks old (published before 2026-11-02). Peer requirements are met: React 19 for all; resolvers 7 accepts `zod ^3.25 || ^4` and `react-hook-form ^7.55`.

## Use cases and existing alternatives

| Package | Intended use | Existing in repo | Why it would be needed |
|---|---|---|---|
| `@tanstack/react-table` | Headless table state: server-side sort/filter/pagination, column visibility, selection, row expansion (`components/data-table/*`) | **None.** 79 hand-rolled `<table>`s, 2 legacy `DataTable`/`AccordionTable`, no sort/selection engine (frontend-audit/03 §1). `@tanstack/react-query` is present, but it handles server state, not table state | Replaces bespoke per-page table state. It is headless, so it adds no visual library. Same vendor and conventions as the TanStack Query already in use |
| `react-hook-form` | Form state with minimal re-renders (`components/form/*`) | **None.** All 9 forms use hand-rolled `useState` (03 §7) | Consistent validation, error display and dirty/submit state |
| `zod` | Schema validation and type inference for forms | **None.** No validation library | Pairs with RHF; also usable for API response typing |
| `@hookform/resolvers` | Adapter connecting zod to RHF | n/a | Only needed if both RHF and zod are approved |

## Current code depending on them

- `src/components/data-table/*` (DataTable, ExpandableDataTable, helpers, types, test) and `src/components/form/*` (Form, fields, test).
- **No other file imports these directories.** All licence, BOE and allotment workspace work uses cards, DetailTabs, ActionMenu and the other `components/shared/*`, none of which depend on the four packages.
- **Reverting is clean:** remove the 4 entries plus their lockfile entries, and delete `components/data-table/` and `components/form/`. Nothing else breaks.

## Security and maintenance assessment

- All four are MIT-licensed, widely used, actively maintained, and have no known advisories at these versions (`npm audit`).
- Combined runtime dependency footprint: 2 transitive packages (`table-core`, `@standard-schema/utils`).
- Maintenance cost: version pinning. zod 4 is a newer major, so its API differs from zod 3 tutorials.

## Recommendation

| Option | Effect |
|---|---|
| **A. Approve all four** (recommended only if shared tables and forms will be adopted next) | Commit them along with `components/data-table` and `components/form` |
| **B. Approve `@tanstack/react-table` only** | Keep DataTable. Remove the form kit and the 3 form packages |
| **C. Approve none** | Revert the 4 packages and delete the two directories. Existing work is unaffected |

Until a decision is made, the packages and the two directories stay **uncommitted**.
