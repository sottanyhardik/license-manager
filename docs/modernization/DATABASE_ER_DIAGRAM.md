# Database ER Diagrams (Phase 1 discovery)

Derived statically from models (see `DATABASE_ARCHITECTURE.md` for file:line). Only keys and money/qty columns shown. `||--o{` = one-to-many, `}o--o{` = M2M. FK on_delete is noted in the relationship label (CAS = CASCADE, PRO = PROTECT, SN = SET_NULL).

## 1. Cross-domain overview
```mermaid
erDiagram
    COMPANY ||--o{ LICENSE : "exporter SN"
    LICENSE ||--o{ IMPORT_ITEM : "CAS"
    IMPORT_ITEM ||--o{ ROW_DETAILS : "sr_number CAS"
    BOE ||--o{ ROW_DETAILS : "CAS"
    BOE }o--o{ ALLOTMENT : "M2M"
    ALLOTMENT ||--o{ ALLOTMENT_ITEM : "CAS"
    IMPORT_ITEM ||--o{ ALLOTMENT_ITEM : "CAS"
    LICENSE_TRADE ||--o{ TRADE_LINE : "CAS"
    IMPORT_ITEM ||--o{ TRADE_LINE : "PRO"
    TRADE_LINE ||--o{ INVOICE_BOE_ALLOC : "PRO"
    ROW_DETAILS ||--o{ INVOICE_BOE_ALLOC : "PRO"
    ROW_DETAILS ||--o{ BOE_ALLOTMENT_ALLOC : "PRO"
    ALLOTMENT_ITEM ||--o{ BOE_ALLOTMENT_ALLOC : "PRO"
    LICENSE_TRADE }o--o{ BOE : "M2M boes"
    COMPANY ||--o{ LICENSE_TRADE : "from/to SN"
    LICENSE ||--|| LICENSE_BALANCE : "O2O pk"
```

## 2. Licence cluster
```mermaid
erDiagram
    LicenseDetailsModel {
        string license_number UK
        date license_expiry_date
    }
    LicenseExportItemModel { decimal net_quantity "15,2" decimal cif_fc "15,2" }
    LicenseImportItemsModel {
        int serial_number "UK with license"
        decimal quantity "15,3"
        decimal cif_fc "15,2"
        decimal available_quantity "15,3 denorm"
        decimal debited_value "15,2 denorm"
        decimal allotted_value "15,2 denorm"
    }
    LicenseItemPlan { decimal planned_quantity "15,3" decimal remaining_quantity "cache" bool is_deleted }
    LicenseBalance { decimal balance_cif "15,2" }
    LicenseFlags { bool is_active }
    LicenseOwnership { fk current_owner }
    LicenseNotes { text notes }
    LicenseDocumentModel { file file }
    LicenseTransferModel { fk from_company fk to_company }
    LicensePurchase { decimal cif_inr "15,2" }
    IncentiveLicense { decimal license_value "15,2" decimal balance_value "15,2" }
    LicenseReplanRequest { string status }
    SionPlanningRule { fk sion_PRO int version }
    SionPlanningProfile { uuid uid UK }
    LicenseDetailsModel ||--o{ LicenseExportItemModel : "CAS"
    LicenseDetailsModel ||--o{ LicenseImportItemsModel : "CAS"
    LicenseDetailsModel ||--o{ LicenseItemPlan : "CAS"
    LicenseImportItemsModel ||--o{ LicenseItemPlan : "CAS"
    LicenseDetailsModel ||--|| LicenseBalance : "O2O"
    LicenseDetailsModel ||--|| LicenseFlags : "O2O"
    LicenseDetailsModel ||--|| LicenseOwnership : "O2O"
    LicenseDetailsModel ||--|| LicenseNotes : "O2O"
    LicenseDetailsModel ||--o{ LicenseDocumentModel : "CAS"
    LicenseDetailsModel ||--o{ LicenseTransferModel : "CAS"
    LicenseDetailsModel ||--o{ LicensePurchase : "CAS"
    LicenseDetailsModel ||--o{ LicenseReplanRequest : "CAS"
    SionPlanningRule ||--o{ LicenseItemPlan : "PRO"
    SionPlanningProfile ||--o{ SionPlanningRule : "via sion"
    SionPlanningProfile ||--o{ SionPlanningRun : "PRO"
    SionPlanningProfile ||--o{ SionPlanningAction : "PRO"
    SionPlanningProfile ||--o{ SionPlanningOutputMapping : "PRO"
    CompanyModel ||--o{ LicenseDetailsModel : "exporter SN"
    CompanyModel ||--o{ IncentiveLicense : "CAS"
    LicenseDetailsModel ||--o{ LicenseLedgerPackageItem : "PRO"
    LicenseLedgerPackageJob ||--o{ LicenseLedgerPackageItem : "CAS"
```
`license_balance_mv`, `item_balance_mv`, `dashboard_stats_mv` are materialized views (not models) over these tables.

## 3. Allotment cluster
```mermaid
erDiagram
    AllotmentModel {
        decimal required_quantity "15,2"
        decimal cif_fc "15,2"
        string invoice "free text"
    }
    AllotmentItems {
        decimal qty "15,3"
        decimal cif_fc "15,2"
        decimal cif_inr "15,2"
        string allocation_basis
        string status
    }
    AllocationVersion { decimal quantity "15,3" decimal cif_fc "15,2" }
    AuditEvent { string action decimal quantity_after "15,3" }
    Shortfall { decimal required_cif "15,2" }
    CompanyModel ||--o{ AllotmentModel : "PRO"
    PortModel ||--o{ AllotmentModel : "PRO"
    AllotmentModel ||--o{ AllotmentItems : "CAS null"
    LicenseImportItemsModel ||--o{ AllotmentItems : "CAS null"
    LicenseItemPlan ||--o{ AllotmentItems : "plan_line SN"
    AllotmentItems ||--o{ AllotmentItems : "previous_version SN"
    AllotmentItems ||--o{ AllocationVersion : "PRO"
    AllotmentItems ||--o{ AuditEvent : "PRO null"
    LicenseDetailsModel ||--o{ Shortfall : "CAS"
    ItemNameModel ||--o{ AllotmentModel : "planning_target PRO"
```

## 4. Bill of Entry cluster
```mermaid
erDiagram
    BillOfEntryModel {
        string bill_of_entry_number "UK with date"
        date bill_of_entry_date "nullable"
        decimal exchange_rate "12,4"
    }
    RowDetails {
        fk sr_number "UK with boe+txn"
        string transaction_type
        decimal qty "15,3"
        decimal cif_fc "15,3"
        decimal cif_inr "15,3"
        bool is_frozen
        bool is_dispute
    }
    BillOfEntryModel ||--o{ RowDetails : "CAS null"
    LicenseImportItemsModel ||--o{ RowDetails : "sr_number CAS"
    BillOfEntryModel }o--o{ AllotmentModel : "allotment M2M"
    CompanyModel ||--o{ BillOfEntryModel : "PRO null"
    PortModel ||--o{ BillOfEntryModel : "PRO null"
    BillOfEntryModel ||--o{ Invoice : "license.Invoice CAS null"
```

## 5. Trade / invoice cluster
```mermaid
erDiagram
    LicenseTrade {
        string direction
        string invoice_number "partial UK per party"
        decimal total_amount "20,2"
    }
    LicenseTradeLine {
        decimal qty_kg "20,4"
        decimal cif_fc "20,2"
        decimal amount_inr "20,2"
    }
    IncentiveTradeLine { decimal license_value "20,2" }
    LicenseTradePayment { decimal amount "20,2" }
    TradeInvoiceDocument { string version_hash "UK with trade" }
    TradePairAudit { uuid pair_uuid }
    SaleClassificationDecision { json licence_ids }
    Invoice { string invoice_number UK decimal total_qty "12,3" }
    InvoiceItem { decimal qty "12,3" decimal cif_fc "15,2" }
    LicenseTrade ||--o{ LicenseTradeLine : "CAS"
    LicenseTrade ||--o{ IncentiveTradeLine : "CAS"
    LicenseTrade ||--o{ LicenseTradePayment : "CAS"
    LicenseTrade ||--o{ TradeInvoiceDocument : "CAS"
    LicenseTrade ||--o{ SaleClassificationDecision : "PRO"
    LicenseTrade ||--o{ TradePairAudit : "SN"
    LicenseTrade ||--o| LicenseTrade : "counterpart O2O PRO"
    LicenseTradeLine ||--o| LicenseTradeLine : "counterpart_line O2O CAS"
    LicenseImportItemsModel ||--o{ LicenseTradeLine : "PRO"
    IncentiveLicense ||--o{ IncentiveTradeLine : "PRO"
    LicenseTrade }o--o{ BillOfEntryModel : "boes M2M"
    CompanyModel ||--o{ LicenseTrade : "from/to SN, final_party PRO"
    InvoiceEntity ||--o{ Invoice : "CAS"
    Invoice ||--o{ InvoiceItem : "CAS"
    LicenseImportItemsModel ||--o{ InvoiceItem : "CAS"
```

## 6. Reconciliation cluster
```mermaid
erDiagram
    InvoiceBOEAllocation {
        decimal allocated_qty "20,4"
        decimal allocated_cif_fc "20,3"
        bool is_current
        string status
    }
    BOEAllotmentAllocation {
        decimal allocated_qty "20,4"
        decimal allocated_cif_fc "20,3"
        bool is_current
        string status
    }
    ExternalInvoiceLink { string invoice_number decimal qty "20,4" bool is_current }
    ReconciliationNote { string status }
    ReconciliationLog { string action json before json after }
    IgnoredWarning { string warning_type "UK with license+entity" }
    LicenseTradeLine ||--o{ InvoiceBOEAllocation : "PRO"
    RowDetails ||--o{ InvoiceBOEAllocation : "PRO"
    RowDetails ||--o{ BOEAllotmentAllocation : "PRO"
    AllotmentItems ||--o{ BOEAllotmentAllocation : "PRO"
    RowDetails ||--o{ ExternalInvoiceLink : "PRO"
    InvoiceBOEAllocation ||--o| InvoiceBOEAllocation : "superseded_by SN"
    BOEAllotmentAllocation ||--o| BOEAllotmentAllocation : "superseded_by SN"
    LicenseTrade ||--o{ ReconciliationNote : "SN"
    BillOfEntryModel ||--o{ ReconciliationNote : "SN"
    LicenseImportItemsModel ||--o{ ReconciliationLog : "SN"
    LicenseDetailsModel ||--o{ IgnoredWarning : "CAS"
```
No DB unique constraint on the three allocation tables (see Finding 1).

## 7. Core masters cluster
```mermaid
erDiagram
    CompanyModel { string iec UK }
    PortModel { string code UK }
    ItemGroupModel { string name UK }
    ItemNameModel { string name UK decimal restriction_percentage "5,2" }
    HSCodeModel { string hs_code UK decimal unit_price "15,2" }
    HeadSIONNormsModel { string name }
    SionNormClassModel { string norm_class UK }
    SIONExportModel { decimal quantity "15,2" }
    SIONImportModel { int serial_number decimal quantity "15,2" }
    SionNormNote { text note_text }
    SionNormCondition { text condition_text }
    ProductDescriptionModel { text product_description }
    ExchangeRateModel { date date UK decimal usd "10,4" }
    SchemeCode { string code UK }
    NotificationNumber { string code UK }
    PurchaseStatus { string code UK }
    ItemGroupModel ||--o{ ItemNameModel : "CAS null"
    SionNormClassModel ||--o{ ItemNameModel : "sion_norm_class SN"
    SionNormClassModel }o--o{ ItemNameModel : "norms M2M"
    HeadSIONNormsModel ||--o{ SionNormClassModel : "CAS"
    SionNormClassModel ||--o{ SIONExportModel : "CAS"
    SionNormClassModel ||--o{ SIONImportModel : "CAS"
    HSCodeModel ||--o{ SIONImportModel : "SN"
    SionNormClassModel ||--o{ SionNormNote : "CAS"
    SionNormClassModel ||--o{ SionNormCondition : "CAS"
    HSCodeModel ||--o{ ProductDescriptionModel : "PRO"
```
All masters except ExchangeRate/Company/Port... carry `MasterSyncMixin` fields (`master_uid`, `sync_version`, `is_tombstone`). Infra tables (`MasterChange`, `CeleryTaskTracker`, `ActivityLog`, 7 `Sync*` tables) omitted.

## 8. Accounts cluster
```mermaid
erDiagram
    User { string username UK string email UK bool is_active }
    RevokedAccessToken { string jti UK datetime expires_at }
    Task { string status string priority }
    TaskRemark { text text }
    Group ||--o{ User : "M2M groups"
    Permission ||--o{ User : "M2M user_permissions"
    User ||--o{ Task : "assigned_to/rejected_by SN"
    Task ||--o{ TaskRemark : "CAS"
    User ||--o{ TaskRemark : "created_by SN"
```
Every `AuditModel` table has `created_by`/`modified_by` FK -> `User` SET_NULL (not drawn). `RevokedAccessToken` has no FK (keyed by `jti`).
