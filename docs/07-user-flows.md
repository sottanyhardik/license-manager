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

    Cron->>LicenseManager: bash sync-masters.sh
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
