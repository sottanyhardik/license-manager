# UI/UX audit

## Method and limitation

Static review covered `AppRoutes`, `TopNav`, `CommandPalette`, route config and automated UI assets. Safe mocked browser checks were attempted, but an initially passing local subset became unavailable on port `41731`; therefore no broad rendered workflow is verified.

## Findings

- **UX-01 P2:** Top navigation (`TopNav.tsx:15-37`) exposes only major groups; reports, masters and admin rely heavily on `CommandPalette.tsx:32-81`. Promote contextual report/master navigation and preserve keyboard palette as an accelerator.
- **UX-02 P2:** `routes/config.js:1-59` declares listed routes `protected:false`, unlike router guards. Consolidate route/path/title/role/nav metadata.
- Forms/tables need a common async-state standard: loading skeleton, empty explanation/action, field error summary, retryable error, destructive confirmation and success feedback.
- Financial/trade screens should use specialised summary cards and explainable calculation drawers; generic tables should share pagination/filter/export/bulk-selection primitives.

## Design-system migration

Define tokenised typography/spacing/colour/focus/contrast, responsive shell/breadcrumbs, accessible inputs/selectors/dates/dialogues/toasts, reusable query table/filter bar and error boundaries. Start with licence planning, allotment allocation, BOE/trade and reconciliation after their data contracts are stable. Add axe, keyboard and mobile tests to the release gate; source presence is not usability verification.
