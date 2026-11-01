# Current UI/UX audit

## Verified static inventory

`AppRoutes.tsx` declares 57 route expressions, including public auth/error paths, protected CRUD, reconciliation, ledger, overview, masters and eleven mapped reports. The frontend has 200 page modules, 72 components, 2 layout modules, 5 route modules, 5 API modules, 14 services, 14 hooks and 3 contexts; previous discovery counted 78 frontend test modules and 18 shadcn primitives. Findings below are **Inferred from static inspection**, unless marked as a running-application observation.

## Limited running-application observation

**Observed in the running application on 2026-10-31; read-only.** Existing authenticated and login browser tabs on the deployed application were inspected without submitting, exporting, editing, deleting, or downloading anything.

| Route | What was observed | What it proves / does not prove |
| --- | --- | --- |
| `/login` | Accessible username/password fields, password-visibility control, forgotten-password link and sign-in control were exposed in the accessibility tree. | Proves this public screen rendered with labelled controls in that session. It does not prove invalid-credential, throttle, reset or redirect behavior. |
| `/bill-of-entries` | Responsive application shell/navigation, title and result count, search, active-filter controls, date/company/port/invoice filters, exports, create link, row-level action controls and pagination were rendered. The screen announced an updating state. | Proves the observed list state exposes dense operational controls and loading/status text. It does not prove authorization for every action, export correctness, keyboard completion, a11y conformance, empty/error states, responsive breakpoints or data correctness. |

No business data values, user identifiers, or document content are reproduced in V1 documentation. These two observations reduce the route-level visual-observation gap only; they are not a production test or acceptance sign-off.

| Priority | Finding | V1 requirement |
| --- | --- | --- |
| P1 | `TopNav` and `routes/config.js` divide navigation ownership; unused-looking `Sidebar` duplicates it. | One typed, role-aware navigation registry; do not remove Sidebar until runtime/bookmark confirmation. |
| P1 | `MasterList`/`MasterForm` centralize six high-value entities through dynamic metadata/path inference and combine forms, parsing, documents, calculations and submissions. | Feature adapters with explicit page state/validation contracts; preserve backend API first. |
| P1 | `ErrorBoundary` retains Bootstrap classes while shared UI is Tailwind/shadcn. | Shared recovery surface with retry, support context and safe correlation ID. |
| P1 | Client role guards can drift from API roles. | Route-to-API role contract tests; backend remains authority. |
| P2 | Loading and error states are inconsistent: Suspense uses `PageLoader`, protected loading is bare text, global failure asks refresh. | Page state policy: skeleton, empty, denial, retry/offline, mutation success/failure. |
| P2 | Generic DataTable derives numeric behavior from field names and cardifies tables on mobile. | Column metadata, precision/provenance, saved views and workflow-specific dense-grid rules. |

Static positives: responsive focus/mobile styles and live regions in `index.css`; keyboard-aware TopNav focus management; `DataTable` skeleton/empty/inline-edit/mobile-label handling; E2E specs for shell, login, licence overview, trade, responsive and accessibility. These require runtime confirmation.
