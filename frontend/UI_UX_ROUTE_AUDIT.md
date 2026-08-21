# UI/UX route audit

Visual scope only. All routes use the shared `AdminLayout` unless noted.

| Route | Component | UI type / visual work | Responsive review | Status |
|---|---|---|---|---|
| `/login` | Login | Focused authentication surface | Auth layout stacks on narrow screens | Complete |
| `/forgot-password` | PasswordReset | Focused authentication form | Single-column controls | Complete |
| `/401`, `/403`, `*` | Unauthorized, Forbidden, NotFound | Error/permission state | Centered narrow-screen state | Complete |
| `/dashboard` | Dashboard | KPI grid, activity tables, chart panels | KPI grid/table overflow | Complete |
| `/licenses`, create, edit | MasterList, MasterForm | Operational list and sectioned form | Filter/form wrapping | Complete |
| `/licenses/:id/overview`, `/balance` | LicenseOverviewPage, redirect | Detail summary/tabs | Internal tab/table scrolling | Complete |
| `/license-ledger`, `/:licenseId/:itemId`, `/ledger-upload` | LicenseLedger, LicenseLedgerDetail, LedgerUpload | Ledger tables/detail/upload state | Internal tables/drop area | Complete |
| `/planning` | LicensePlanningWorkspace | SION workbench, dense rule tables/forms | Responsive rule workbench | Complete |
| `/allotments`, create, edit, allocate | MasterList, MasterForm, AllotmentAction | Lists/forms/allocation panels | Toolbar/form stacking | Complete |
| `/bill-of-entries`, create, edit, transfer-letter | MasterList, MasterForm, BOETransferLetter | Lists/forms/document action | Internal table/form scroll | Complete |
| `/trades`, create, edit | MasterList, TradeForm | List and financial form | Responsive field groups | Complete |
| `/reconciliation`, `/reconciliation-issues` | ReconciliationPanel, ReconciliationIssues | Severity/result tables | Internal table scrolling | Complete |
| `/incentive-licenses`, create, edit | MasterList, MasterForm | List/form | Responsive filters/forms | Complete |
| `/reports/parle/sion-e1`, `e5`, `e126`, `e132` | SionE1/E5/E126/E132 | Report parameters/results | Internal table scrolling | Complete |
| `/reports/expiring-licenses`, `/active-licenses`, `/download-license` | ExpiringLicenses, ActiveLicenses, DownloadLicense | Report lists/download | Responsive result states | Complete |
| `/reports/item-pivot`, `/item-report`, `/planned-report`, `/license-purchase-profit` | ItemPivotReport, ItemReport, PlannedReport, LicensePurchaseProfitReport | Dense reporting/filter surfaces | Filter wrapping/table scroll | Complete |
| `/pdf-viewer` | PDFViewer | Document viewing surface | Full viewport viewer | Complete |
| `/settings`, `/profile` | Settings, Profile | Account/settings forms | Single column on mobile | Complete |
| `/masters/:entity`, create, edit | MasterList, MasterForm | Reusable master list/form | Filter/form responsiveness | Complete |
| `/admin/users`, create, edit, `/admin/activity-log` | UserList, UserForm, ActivityLog | Admin list/form/audit table | Toolbar/form/table responsiveness | Complete |

Shared visual components reviewed: `AdminLayout`, `TopNav`, `PageHeader`, `StatCard`, `DataTable`, `FormField`, `EmptyState`, `ConfirmDialog`, loading, toast, dropdown and pagination primitives.
