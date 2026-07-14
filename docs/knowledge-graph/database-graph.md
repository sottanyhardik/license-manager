# Database Graph

> Living document. Single shared PostgreSQL database.
> Full ER diagrams and table inventory: `docs/05-database.md`
> Full cascade risk register: `docs/05-database.md` §4

## Strategy

- One PostgreSQL instance shared by `legacy/backend/` and `backend/`
- All migrations from `backend/` must be **additive-only** during transition
- No DROP TABLE, no DROP COLUMN, no data-destructive changes until final cutover
- New tables use `AuditModel` base (`created_at`, `updated_at`, `deleted_at`, `created_by`)

## App → Table Ownership

| Django App | Tables | Migration Status |
|---|---|---|
| accounts | `accounts_user` | legacy-owned |
| core | `core_companymodel`, `core_portmodel`, `core_hscodemodel`, `core_itemheadmodel` (deprecated), `core_itemgroupmodel`, `core_itemnamemodel`, `core_headsiononormsmodel`, `core_sionnormclassmodel`, `core_sionexportmodel`, `core_sionimportmodel`, `core_sionnormnote`, `core_sionnormcondition`, `core_productdescriptionmodel`, `core_transferlettermodel`, `core_unitpricemodel`, `core_invoiceentity`, `core_schemecode`, `core_notificationnumber`, `core_purchasestatus`, `core_exchangeratemodel`, `core_celerytasktracker`, `core_activitylog`, `core_masterchange` | legacy-owned |
| license | `license_licensedetailsmodel`, `license_licensenotes`, `license_licensebalance`, `license_licenseflags`, `license_licenseownership`, `license_licenseexportitemmodel`, `license_licenseimportitemsmodel`, `license_licenseitemplan`, `license_licensedocumentmodel`, `license_statusmodel`, `license_officemodel`, `license_alongwithmodel`, `license_datemodel`, `license_licenseinwardoutwardmodel`, `license_licensetransfermodel`, `license_incentivelicense`, `license_licensepurchase`, `license_invoice`, `license_invoiceitem` | legacy-owned |
| allotment | `allotment_allotmentmodel`, `allotment_allotmentitems` | legacy-owned |
| bill_of_entry | `bill_of_entry_billofentrymodel`, `bill_of_entry_rowdetails` | legacy-owned |
| trade | `trade_licensetrade`, `trade_licensetradelline`, `trade_incentivetradeline`, `trade_licensetradeepayment` | legacy-owned |
| tasks | `tasks_task`, `tasks_taskremark` | legacy-owned |

## High-Risk Cascades (from Phase 1 audit)

| Table | Risk | Reason |
|---|---|---|
| LicenseDetailsModel | HIGH | 5+ dependent tables via FK |
| CompanyModel | HIGH | Referenced by BOE, Allotment, License, Trade |
| bill_of_entry.BillOfEntryModel | HIGH | on_delete=CASCADE on company, port |
| SionNormClassModel | HIGH | Linked to license items |

See full register in `docs/05-database.md` §4.

## New Tables (added by backend/)

> Populated as modules are implemented. Each entry must note whether it is additive-only.

| Table | Module | Migration | Additive? |
|---|---|---|---|
| (none yet) | | | |
