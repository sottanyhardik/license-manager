# 07 — User Flows

---

## UF-01: Login

```mermaid
graph LR
    Start([Open App]) --> Check{Token in\nlocalStorage?}
    Check -->|Yes| Verify[Auto-verify token]
    Check -->|No| LoginPage[Show Login Page]
    Verify -->|Valid| Dashboard
    Verify -->|Invalid/Expired| RefreshTry[Try refresh token]
    RefreshTry -->|Success| Dashboard
    RefreshTry -->|Fail| LoginPage
    LoginPage --> Submit[Submit username + password]
    Submit --> API[POST /api/auth/login/]
    API -->|200| StoreTokens[Store access + refresh in localStorage]
    StoreTokens --> Dashboard[Navigate to Dashboard]
    API -->|401| Error[Show error message]
```

**Session Management**:
- Access token refreshed proactively 5 min before expiry
- After 30 min idle → auto-logout to `/login?reason=idle`
- After session expiry → `/login?reason=session_expired`

---

## UF-02: Create a New DFIA License

```mermaid
graph TD
    A([Navigate /licenses/create]) --> B[MasterForm loads\nempty license template]
    B --> C[Fill header fields\n- license_number\n- dates\n- exporter\n- port\n- SION norm]
    C --> D[Add import items\n via NestedFieldArray]
    D --> E[Optional: Upload License PDF\nfor OCR parsing]
    E --> F{OCR result?}
    F -->|Fields detected| G[Review suggested\npre-fill values]
    G --> H[Confirm / adjust]
    F -->|No PDF| H
    H --> I[Save]
    I --> J[POST /api/licenses/]
    J -->|Success| K[Sub-tables auto-created\nvia signal]
    K --> L[Redirect to license detail\nor list]
    J -->|Validation error| M[Show field errors]
    M --> H
```

---

## UF-03: Upload Government Ledger File (Async)

```mermaid
sequenceDiagram
    participant User
    participant LedgerUpload Page
    participant Backend
    participant Celery
    participant DB

    User->>LedgerUpload Page: Select CSV/HTM files
    User->>LedgerUpload Page: Click Upload
    LedgerUpload Page->>Backend: POST /api/upload-ledger/ (multipart)
    Backend->>Backend: Parse file headers
    Backend->>Celery: Queue one task per license row
    Backend-->>LedgerUpload Page: {tasks: [{license, task_id}]}
    LedgerUpload Page->>LedgerUpload Page: Show progress modal
    loop Poll every 1 second
        LedgerUpload Page->>Backend: GET /api/ledger-task-status/:task_id
        Backend->>Celery: Check task state
        Celery-->>Backend: {state, progress}
        Backend-->>LedgerUpload Page: {state, progress}
        LedgerUpload Page->>LedgerUpload Page: Update progress bar
    end
    Celery->>DB: Create frozen RowDetails\nUpdate import item balances
    LedgerUpload Page->>User: Show completion summary\n(done / failed per license)
```

---

## UF-04: Create an Allotment

```mermaid
graph TD
    A([Navigate /allotments/create]) --> B[Fill allotment header\n- company\n- port\n- type AT/TR\n- CIF values]
    B --> C[Add allotment items\n via NestedFieldArray\n- link to import items\n- enter required_quantity]
    C --> D[Verify available balance\nnot exceeded]
    D --> E[Save]
    E --> F[POST /api/allotments/]
    F -->|Success| G[Signal updates\nallotted_quantity on import items]
    G --> H[Navigate to\n/allotments/:id/allocate]
    H --> I{Generate Transfer Letter?}
    I -->|Yes| J[TransferLetterForm\n- select parties\n- select template\n- review CIF\n- generate ZIP/PDF]
```

---

## UF-05: Generate a Transfer Letter

```mermaid
graph TD
    A([From Allotment / BOE / Trade page]) --> B[Click Transfer Letter action]
    B --> C[TransferLetterForm opens\nor TransferLetterModal]
    C --> D[Select license groups\nto include]
    D --> E[Add party row\n- company name / address\n- template selection]
    E --> F{More parties?}
    F -->|Yes| E
    F -->|No| G[Optionally edit CIF values]
    G --> H[Choose format:\nZIP / PDF / Without Sign]
    H --> I[POST .../generate-transfer-letter/]
    I --> J[Backend renders DOCX\nvia docxtpl]
    J --> K{Format?}
    K -->|ZIP| L[Download .zip\n containing one DOCX per party]
    K -->|PDF| M[Download combined PDF]
    K -->|Preview| N[Open in browser PDF viewer]
```

---

## UF-06: License Ledger Review

```mermaid
graph TD
    A([Navigate /license-ledger]) --> B[Select company\nfrom async dropdown]
    B --> C[Optionally filter:\n- license type\n- date range\n- ordering]
    C --> D[GET /api/license-ledger/\n?company=ID&purchase_date_from=...&...]
    D --> E[Display ledger grouped\nby license]
    E --> F{Drill down?}
    F -->|Click license| G[Navigate to\n/license-ledger/:id\n?license_type=DFIA]
    G --> H[LicenseLedgerDetail\nshows transaction-by-transaction\nwith running balance]
    H --> I{Export?}
    I -->|PDF| J[generatePDF()]
    I -->|Excel| K[generateExcel()]
    F -->|No| L[View summary table]
```

---

## UF-07: Dashboard Situational Awareness

```mermaid
graph LR
    A([Open Dashboard /]) --> B[GET /api/dashboard/]
    B --> C[License KPIs\n- total / active / expired\n- null DFIA / expiring soon]
    B --> D[Operations KPIs\n- allotments / BOE / pending invoices]
    B --> E[Expiring Licenses\ntable next 30 days]
    B --> F[BOE Monthly Trend\nchart last 6 months]
    B --> G[Recent BOE records]
    B --> H[Recent Allotments]
    C --> I[Click expiring soon\n→ /reports/expiring-licenses]
    D --> J[Click view all\n→ /bill-of-entries]
```

---

## UF-08: Task Management via Voice

```mermaid
graph TD
    A([Click TaskFAB button]) --> B[TaskDrawer slides in]
    B --> C{Voice input available?}
    C -->|Yes| D[Click mic icon]
    D --> E[Speak: title + assignee + priority\ne.g. 'Check BOE for Labdhi\nassign to ankit urgent']
    E --> F[Speech Recognition API\nparses text]
    F --> G[Auto-extract:\n- title: 'Check BOE for Labdhi'\n- assignee: fuzzy match 'ankit' → user ID\n- priority: HIGH\nbecause 'urgent' keyword]
    G --> H[POST /api/tasks/]
    H --> I[Task created\nShown in list]
    C -->|No| J[Manual form entry\n- title / description\n- priority\n- assignee\n- due date]
    J --> H
```

---

## UF-09: User & Role Management

```mermaid
graph TD
    A([Navigate /admin/users\nSuperuser or USER_MANAGER]) --> B[GET /api/auth/users/]
    B --> C[User list with search/filter\nby role, active status]
    C --> D{Action}
    D -->|Create| E[POST /api/auth/users/\nUsername + email + password\n+ role checkboxes]
    D -->|Edit| F[PATCH /api/auth/users/:id/\nUpdate details/roles]
    D -->|Reset password| G[POST /api/auth/users/:id/reset-password/]
    D -->|Deactivate| H[PATCH is_active=false\nUser cannot login]
    E --> I[User added\nRoles applied as Django Groups]
```

---

## UF-10: BOE Balance PDF Generation

```mermaid
graph TD
    A([On license detail page\nClick Balance PDF]) --> B[GET /api/licenses/:id/balance_pdf/]
    B --> C[Backend gathers:\n- license header\n- all import items\n- per-company BOE debits\n- allotment totals\n- CIF INR from RowDetails]
    C --> D[ReportLab renders multi-page PDF]
    D --> E[Browser opens PDF\nfor download/print]
```

---

## UF-11: Master Data Sync Between Servers

```mermaid
sequenceDiagram
    participant Cron
    participant LicenseManager as license-manager (canonical)
    participant Labdhi as labdhi (follower)
    participant Tractor as tractor (follower)

    Cron->>LicenseManager: bash scripts/maintenance/sync-masters.sh
    LicenseManager->>LicenseManager: python manage.py audit_masters\n→ /tmp/sync-audit.json
    LicenseManager-->>Cron: sync-audit.json

    Cron->>Labdhi: SCP sync-audit.json
    Cron->>Labdhi: python manage.py auto_import_masters\n--sources sync-audit.json --apply --update-existing
    Labdhi-->>Cron: imported=N, updated=M, failed=K

    Cron->>Tractor: SCP sync-audit.json
    Cron->>Tractor: python manage.py auto_import_masters\n--sources sync-audit.json --apply --update-existing
    Tractor-->>Cron: imported=N, updated=M, failed=K

    Note over Cron: Failures saved to failed-*.csv\nExit code 2 if any failures (triggers cron email)
```

---

## UF-12: Delete a Trade (Purchase/Sale)

```mermaid
sequenceDiagram
    participant User
    participant TradesListView
    participant MasterList as MasterList.tsx
    participant API
    participant Backend as LicenseTradeViewSet
    participant Signal as Django Signals
    participant DB

    User->>TradesListView: Click trash icon on a trade row
    TradesListView->>MasterList: onDelete(tradeItem)
    MasterList->>User: Show confirmation dialog
    User->>MasterList: Confirm delete
    MasterList->>API: DELETE /api/trade/trades/:id/
    API->>Backend: destroy(pk)
    Backend->>Backend: get_object() — fetch trade
    Backend->>Signal: pre_delete signals fire

    alt trade has counterpart
        Signal-->>Backend: ValidationError (prevent_single_counterpart_delete)
        Backend-->>API: 400 Bad Request
        API-->>MasterList: Error response
        MasterList->>User: Toast: "This trade has a linked counterpart..."
    else trade has linked BOEs
        Signal->>DB: Clear invoice_no/invoice_date on matching BOEs
    else no constraints
        Signal-->>Backend: OK
    end

    alt delete allowed
        Backend->>DB: instance.delete()
        DB->>DB: CASCADE delete LicenseTradeLine, IncentiveTradeLine,<br/>LicenseTradePayment, TradeInvoiceDocument,<br/>InvoiceDocumentAccessToken, InvoiceDocumentAuditEvent
        DB->>DB: Clear boes M2M relation
        Backend-->>API: 204 No Content
        API-->>MasterList: Success
        MasterList->>MasterList: invalidateList() — refresh trade list
        MasterList->>User: Toast: "Record deleted successfully"
    end
```

**Key points**:
- Only `TRADE_MANAGER` role can delete
- Paired trades (with `counterpart`) are **blocked** from single-side deletion
- Linked BOE invoice references are cleared, not deleted
- Child objects (lines, payments, documents) are CASCADE-deleted

---

## UF-14: Force Delete a Trade (Manual Override via Django Shell)

**Trigger**: When a trade must be deleted despite having a counterpart, audit records, or classification decisions — e.g., data cleanup after testing or error recovery.

```mermaid
sequenceDiagram
    participant Admin
    participant Shell as Django Shell
    participant Models as Trade Models
    participant DB

    Admin->>Shell: Open Django shell (python manage.py shell)
    Shell->>Models: Import LicenseTrade, TradePairAudit, SaleClassificationDecision

    Note over Admin,DB: Step 1: Clear counterpart link
    Admin->>Shell: trade = LicenseTrade.objects.get(pk=<ID>)
    Shell->>Models: Fetch trade and counterpart
    Admin->>Shell: trade.counterpart = None; trade.save()
    alt counterpart exists
        Admin->>Shell: counterpart.counterpart = None; counterpart.save()
    end
    Models->>DB: Update counterpart = NULL on both trades

    Note over Admin,DB: Step 2: Delete protecting audit records
    Admin->>Shell: TradePairAudit.objects.filter(source=trade).delete()
    Models->>DB: Delete TradePairAudit records
    Admin->>Shell: TradePairAudit.objects.filter(counterpart=trade).delete()
    Models->>DB: Delete more TradePairAudit records
    Admin->>Shell: SaleClassificationDecision.objects.filter(trade=trade).delete()
    Models->>DB: Delete SaleClassificationDecision records

    Note over Admin,DB: Step 3: Delete the trade
    Admin->>Shell: trade.delete()
    Models->>DB: CASCADE delete LicenseTradeLine, IncentiveTradeLine,<br/>LicenseTradePayment, TradeInvoiceDocument,<br/>InvoiceDocumentAccessToken, InvoiceDocumentAuditEvent
    Models->>DB: Clear boes M2M relation
    Models-->>Shell: Trade deleted
    Shell-->>Admin: Confirmation

    Note over Admin,DB: ⚠️ Audit trail permanently destroyed
```

**Key points**:
- No API endpoint exists for force delete — must use Django shell or direct database operations
- Requires Django superuser access
- The `counterpart` link must be cleared on **both** trades before deletion
- `TradePairAudit` and `SaleClassificationDecision` records must be deleted to satisfy PROTECT FK constraints
- `QuerySet.delete()` bypasses `pre_delete` signals but NOT `PROTECT` FK constraints
- Linked BOE invoice references are **NOT** cleared when using `QuerySet.delete()` (signals are bypassed)
- Use only for data cleanup, error recovery, or database maintenance — not for normal operations

---

## UF-15: Create Direct SALE Trade — Quantity Validation Error

**Trigger**: User creates a SALE trade without BOEs (direct sale bypass path), and the requested quantity exceeds the available quantity for one or more import items.

```mermaid
sequenceDiagram
    participant User
    participant TradeForm as TradeForm.tsx
    participant API
    participant Serializer as LicenseTradeSerializer
    participant Calculator as ItemBalanceCalculator
    participant DB

    User->>TradeForm: Fill SALE trade form (no BOEs selected)
    User->>TradeForm: Add line items with quantities
    User->>TradeForm: Submit form
    TradeForm->>API: POST /api/trade/trades/
    API->>Serializer: create(validated_data)
    Serializer->>Serializer: Check direction==SALE AND boes is empty
    alt validation triggered
        Serializer->>DB: select_for_update() on each import item
        Serializer->>Calculator: calculate_available_quantity(item)
        Calculator->>DB: Read item.quantity (total)
        Calculator->>DB: Sum RowDetails DEBIT qty (BOE debited)
        Calculator->>DB: Get outstanding allotment qty
        Calculator->>DB: Sum unpaired direct SALE qty
        Calculator-->>Serializer: available = total - debited - allotted - directSale
        alt requested > available
            Serializer-->>API: ValidationError
            API-->>TradeForm: 400 {"lines": "SALE quantity X exceeds..."}
            TradeForm->>User: Display error message
        else requested <= available
            Serializer->>DB: Create trade and lines
            Serializer-->>API: 201 Created
            API-->>TradeForm: Trade data
            TradeForm->>User: Success, navigate to trade list
        end
    else BOEs attached — validation skipped
        Serializer->>DB: Create trade and lines
        Serializer-->>API: 201 Created
        API-->>TradeForm: Trade data
        TradeForm->>User: Success
    end
```

**Key points**:
- Validation only fires for SALE trades with no BOEs (`boes: []`)
- When BOEs are attached, the validation is skipped — the BOE linkage serves as the physical quantity debit
- Row locks (`select_for_update()`) prevent concurrent over-consumption
- The error message identifies the specific import item and shows both requested and available quantities
- User must either reduce quantities or attach BOEs to bypass the validation

---

## UF-13: Copy Trade to Counterpart (Purchase ↔ Sale)

```mermaid
sequenceDiagram
    participant User
    participant TradesListView
    participant MasterList as MasterList.tsx
    participant API
    participant Backend as EnhancedLicenseTradeViewSet
    participant Service as trade_service.py
    participant DB

    User->>TradesListView: Click "Copy to Purchase/Sale" button
    TradesListView->>MasterList: onCopyToCounterpart(tradeItem)
    MasterList->>User: Show confirmation dialog
    User->>MasterList: Confirm
    MasterList->>API: POST /api/trade/trades/:id/copy-to-purchase/ or copy-to-sale/
    API->>Backend: copy_to_purchase / copy_to_sale(pk)
    Backend->>Service: copy_sale_to_purchase() or copy_purchase_to_sale()
    Service->>DB: Create counterpart trade with shared transaction_pair_uuid
    Service->>DB: Link counterpart FK both ways
    Service->>DB: Create TradePairAudit record
    Service-->>Backend: (source, counterpart, created)
    Backend-->>API: 201 Created or 200 OK (if already exists)
    API-->>MasterList: Response with counterpart info
    MasterList->>MasterList: invalidateList()
    MasterList->>User: Navigate to counterpart edit page
```
