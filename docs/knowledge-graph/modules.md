# Modules

> Living document. Add a row per module as it is implemented in `backend/`.
> Status: pending = not started, in-progress = being built, done = feature-parity achieved.

## Backend Modules

| Module | Status | Purpose | Key Tables | Services | APIs Exposed |
|---|---|---|---|---|---|
| accounts | pending | User auth, JWT, RBAC (12 roles) | accounts_user | - | /api/v1/auth/ |
| core | pending | Master data (company, port, HS code, SION, exchange rates) | 17 master tables | - | /api/v1/masters/ |
| license | pending | DFIA + incentive licenses, balance, ledger, reports | license_*, licensebalance | - | /api/v1/licenses/ |
| allotment | pending | Pre-auth allotments + transfer letters | allotment*, allotmentitems | - | /api/v1/allotments/ |
| bill_of_entry | pending | BOE header + row details | billofentry*, rowdetails | - | /api/v1/bill-of-entries/ |
| trade | pending | Trade invoices, lines, payments, PDFs | licensetrade*, tradelinesmodel | - | /api/v1/trades/ |
| tasks | pending | Internal workflow task management | task, taskremark | - | /api/v1/tasks/ |

## Frontend Feature Modules

| Feature | Status | Routes | Key Components | API Hooks |
|---|---|---|---|---|
| auth | pending | /login, /logout | LoginForm | useLogin, useLogout |
| licenses | pending | /licenses, /licenses/:id | LicenseList, LicenseDetail | useLicenses, useLicense |
| allotments | pending | /allotments | AllotmentForm | useAllotments |
| bill-of-entry | pending | /boe | BOEList, BOEDetail | useBOEs |
| trade | pending | /trade | TradeForm | useTrades |
| reports | pending | /reports/* | ReportViewer | useReport |
| masters | pending | /masters/* | MasterList | useMasters |
| tasks | pending | /tasks | TaskDrawer | useTasks |
| dashboard | pending | / | Dashboard | useDashboard |
| settings | pending | /settings | SettingsPanel | - |
