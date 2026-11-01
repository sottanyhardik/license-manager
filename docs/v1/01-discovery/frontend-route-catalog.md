# Frontend route catalog

**Verified by code.** 57 route expressions are declared: 11 report-array routes and 46 literal `<Route>` paths. Public paths are login, password reset, 401/403 and catch-all; protected paths cover dashboard, licences, allotments/planning, BOEs, trade, reconciliation, incentive licences, ledgers, PDF viewer, settings/profile, masters and user administration.

| Family | Literal/report routes | UI owner | Client gate |
| --- | ---: | --- | --- |
| Auth/errors/root | 5 | Login, PasswordReset, error pages | Public / authenticated redirect |
| Dashboard/licence/planning | 6 | Dashboard, MasterList/Form, planning workspace | licence roles |
| Allotment | 4 | MasterList/Form, AllotmentAction | allotment roles |
| Reports | 11 | report page modules | `REPORT_ROLES` |
| BOE | 4 | MasterList/Form, transfer letter | BOE/TL/account roles |
| Trade/reconciliation | 5 | MasterList, TradeForm, reconciliation pages | trade/BOE/account roles |
| Incentive/ledger | 10 | MasterList/Form, ledger upload/detail/package pages | incentive / licence-trade-ledger roles |
| Overview/PDF/settings/profile | 5 | overview, viewer, settings/profile | mixed / superuser |
| Masters/admin | 7 | generic master and user/activity pages | generic or USER_MANAGER |
| Fallback | 1 | NotFound | public |

`ProtectedRoute` is a client usability control; it is not server authorization. Exact page/API mapping and runtime visual inspection remain M1 work.
