# Filter QA Route Inventory

**Generated:** 2026-09-25  
**Mission:** Discover every route and document filter status

## Public Routes (No Filters Expected)

| Route | Component | Filters? | Notes |
|-------|-----------|----------|-------|
| `/login` | Login | No | Authentication page |
| `/forgot-password` | PasswordReset | No | Auth page |
| `/401` | Unauthorized | No | Error page |
| `/403` | Forbidden | No | Error page |
| `*` | NotFound | No | 404 page |

## Main Navigation Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/` | Navigate to /dashboard | No | N/A | N/A |
| `/dashboard` | Dashboard | ? | TBD | TBD |
| `/settings` | Settings | No | Admin only | N/A |
| `/profile` | Profile | No | User profile | N/A |
| `/pdf-viewer` | PDFViewer | No | Utility page | N/A |

## License CRUD Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/licenses` | MasterList | YES | Search, sort, filters | TBD |
| `/licenses/create` | MasterForm | No | Form page | N/A |
| `/licenses/:id/edit` | MasterForm | No | Form page | N/A |
| `/licenses/:id/overview` | LicenseOverviewPage | YES | Tabs, embedded tables | TBD |
| `/licenses/:id/balance` | RedirectToLicenseOverview | No | Redirect | N/A |
| `/planning` | LicensePlanningWorkspace | YES | Search, grid filters | TBD |

## Allotment CRUD Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/allotments` | MasterList | YES | Search, sort, filters | TBD |
| `/allotments/create` | MasterForm | No | Form page | N/A |
| `/allotments/:id/edit` | MasterForm | No | Form page | N/A |
| `/allotments/:id/allocate` | AllotmentAction | YES | Form filters | TBD |

## Report Routes (11 reports)

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/reports/parle/sion-e1` | SionE1 | YES | Company, status filters | TBD |
| `/reports/parle/sion-e5` | SionE5 | YES | Company, status filters | TBD |
| `/reports/parle/sion-e126` | SionE126 | YES | Company, status filters | TBD |
| `/reports/parle/sion-e132` | SionE132 | YES | Company, status filters | TBD |
| `/reports/expiring-licenses` | ExpiringLicenses | YES | Company filters | TBD |
| `/reports/active-licenses` | ActiveLicenses | YES | Company filters | TBD |
| `/reports/download-license` | DownloadLicense | YES | Company filters | TBD |
| `/reports/item-pivot` | ItemPivotReport | YES | Company, balance, status filters | YES (Badge) |
| `/reports/item-report` | ItemReport | YES | 12+ filters (complex) | YES (Inline) |
| `/reports/planned-report` | PlannedReport | YES | 12+ filters (complex) | YES (Inline) |
| `/reports/license-purchase-profit` | LicensePurchaseProfitReport | YES | License, date filters | TBD |

## Bill of Entry CRUD Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/bill-of-entries` | MasterList | YES | Search, sort, filters | TBD |
| `/bill-of-entries/create` | MasterForm | No | Form page | N/A |
| `/bill-of-entries/:id/edit` | MasterForm | No | Form page | N/A |
| `/bill-of-entries/:id/generate-transfer-letter` | BOETransferLetter | No | Report page | N/A |

## Trade CRUD Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/trades` | MasterList | YES | Search, sort, filters | TBD |
| `/trades/create` | TradeForm | No | Form page | N/A |
| `/trades/:id/edit` | TradeForm | No | Form page | N/A |

## Reconciliation Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/reconciliation` | ReconciliationPanel | YES | Tab filters, status | TBD |
| `/reconciliation-issues` | ReconciliationIssues | YES | Status filters | TBD |

## Incentive License CRUD Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/incentive-licenses` | MasterList | YES | Search, sort, filters | TBD |
| `/incentive-licenses/create` | MasterForm | No | Form page | N/A |
| `/incentive-licenses/:id/edit` | MasterForm | No | Form page | N/A |

## Ledger Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/ledger-upload` | LedgerUpload | No | Upload utility | N/A |
| `/license-ledger` | LicenseLedger | YES | Company, type, search, dates | NO (Missing!) |
| `/license-ledger/:licenseId` | LicenseLedgerDetail | YES | Transaction filters | TBD |
| `/license-ledger/:licenseId/:itemId` | LicenseLedgerDetail | YES | Transaction filters | TBD |
| `/license-ledger/download-requests` | LicenseDownloadRequests | YES | Status, date filters | TBD |
| `/license-ledger/download-requests/:requestId` | LicenseDownloadRequestDetail | YES | Item filters | TBD |
| `/license-ledger/package-readiness/:jobId` | LicenseLedgerPackageReadiness | YES | Status filters | TBD |

## Master List (Generic) Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/masters/:entity` | MasterList | YES | Search, sort, filters | TBD |
| `/masters/:entity/create` | MasterForm | No | Form page | N/A |
| `/masters/:entity/:id/edit` | MasterForm | No | Form page | N/A |

## Admin Routes

| Route | Component | Filters? | Filter Types | Active Filters Display |
|-------|-----------|----------|--------------|------------------------|
| `/admin/users` | UserList | YES | Role, status filters | TBD |
| `/admin/users/create` | UserForm | No | Form page | N/A |
| `/admin/users/:id/edit` | UserForm | No | Form page | N/A |
| `/admin/activity-log` | ActivityLog | YES | Action, module filters | TBD |

## Summary

- **Total Routes:** 57
- **Form/Utility Routes (No Filters):** 15
- **Routes with Likely Filters:** 42
- **Routes with Active Filters Component:** 2 (ItemReport, PlannedReport)
- **Routes Missing Active Filters:** 40+ (Need implementation)

## Next Steps

1. Verify filter presence in each component
2. Create FILTER_DISCOVERY.md with detailed filter list
3. Implement ActiveFilters component for all filterable pages
4. Build automated test utilities
5. Execute systematic filter testing
6. Document bugs and fixes
