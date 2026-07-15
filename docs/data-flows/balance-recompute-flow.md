# Balance Recompute — Data Flow

> **Complete data flow from trigger to database write.**

---

## Flow 1: After Allotment Create

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as Django API
    participant DB as PostgreSQL
    participant Redis as Redis /2
    participant Worker as Celery Worker

    User->>FE: Click "Create Allotment"
    FE->>API: POST /api/v1/allotments/ {items: [{item:42, qty:100, cif_fc:1000}]}
    
    activate API
    API->>API: AllotmentPermission.has_permission() → True
    API->>API: AllotmentSerializer.is_valid() → True
    API->>DB: BEGIN TRANSACTION
    
    API->>DB: SELECT FOR UPDATE FROM license_licenseitemplan WHERE import_item_id=42
    Note over DB: Row-level lock prevents concurrent over-allotment
    API->>API: _validate_plan_availability(42, qty=100, cif=1000) → OK (100 <= 500)
    
    API->>DB: INSERT INTO allotment_allotmentmodel (...) → allotment_id=7
    API->>DB: INSERT INTO allotment_allotmentitems (allotment_id=7, item_id=42, qty=100)
    API->>DB: UPDATE license_licenseitemplan SET planned_quantity=planned_quantity-100 WHERE id=...
    Note over DB: F() expression: atomic, no read-modify-write race
    
    API->>DB: COMMIT
    Note over DB: on_commit fires now
    
    API->>API: _dispatch([42]) → resolves license_id
    API->>DB: SELECT license_id FROM license_licenseimportitemsmodel WHERE id=42 → 15
    API->>Redis: recompute_license_balance_task.delay(license_id=15)
    
    API-->>FE: 201 {success:true, data:{id:7, ...}}
    deactivate API
    
    Note over FE: FE shows success, invalidates query cache
    FE->>FE: queryClient.invalidateQueries(['allotments'])

    Redis-->>Worker: deliver task message
    
    activate Worker
    Worker->>DB: BEGIN TRANSACTION
    Worker->>DB: SELECT FOR UPDATE FROM license_licensedetailsmodel WHERE id=15
    Worker->>DB: SELECT SUM(cif_fc) FROM license_licenseexportitemmodel WHERE license_id=15 → credit=50000
    Worker->>DB: SELECT SUM(cif_fc) FROM bill_of_entry_rowdetails WHERE sr_number__license_id=15 ... → debit=5000
    Worker->>DB: SELECT SUM(cif_fc) FROM allotment_allotmentitems WHERE item__license_id=15 AND allotment__bill_of_entry__isnull=True → allotment=1000
    Worker->>DB: SELECT SUM(cif_fc) FROM trade_licensetradelline WHERE sr_number__license_id=15 ... → trade=0
    Note over Worker: balance = max(0, 50000-5000-1000-0) = 44000.00
    Worker->>DB: UPDATE license_licensebalance SET balance_cif=44000.00 WHERE license_id=15
    Worker->>DB: UPDATE license_licenseflags SET is_null=False, is_expired=False WHERE license_id=15
    Worker->>DB: UPDATE license_licenseimportitemsmodel SET allotted_quantity=100, available_quantity=900 ... WHERE license_id=15
    Worker->>DB: COMMIT
    Worker->>Redis: ACK task message
    deactivate Worker
    
    Note over FE: Next poll/navigation refreshes balance display
```

---

## Flow 2: After BOE Row Creation

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as Django API
    participant DB as PostgreSQL
    participant Redis as Redis /2
    participant Worker as Celery Worker

    User->>FE: Click "Add Row" on BOE detail
    FE->>API: POST /api/v1/bill-of-entries/{boe_id}/rows/ {sr_number:42, cif_fc:800, qty:80, transaction_type:"D"}
    
    activate API
    API->>DB: INSERT INTO bill_of_entry_rowdetails (bill_of_entry_id={boe_id}, sr_number_id=42, cif_fc=800, qty=80, transaction_type="D")
    Note over DB: Django post_save signal fires immediately
    DB-->>API: post_save signal: update_stock(sender=RowDetails, instance=row)
    
    API->>API: sr = instance.sr_number → license_id = sr.license_id = 15
    API->>DB: COMMIT (if in transaction) 
    Note over DB: on_commit callback registered
    API->>Redis: recompute_license_balance_task.delay(license_id=15)
    
    Note over DB: Also: recalc_exchange_rate signal fires
    API->>DB: UPDATE bill_of_entry_billofentrymodel SET exchange_rate=... WHERE id={boe_id}
    
    API-->>FE: 201 {success:true, data:{...}}
    deactivate API

    Redis-->>Worker: deliver task
    Worker->>DB: Recompute balance (debit increases by 800)
    Note over Worker: balance = max(0, 50000 - (5000+800) - 0 - 0) = 44200.00
    Note over Worker: If allotment was linked to this BOE: allotment exits formula
    Worker->>DB: UPDATE LicenseBalance, LicenseFlags, LicenseImportItemsModel
```

---

## Flow 3: Balance Recompute Detail

```mermaid
flowchart TD
    START[recompute_license_balance_task.delay license_id] --> T1

    T1[Begin transaction.atomic] --> T2
    T2[SELECT FOR UPDATE LicenseDetailsModel pk=license_id] --> T3
    T3{License exists?}
    T3 -- No --> T4[Log WARNING; return]
    T3 -- Yes --> T5

    T5[_compute_credit: SUM export items cif_fc] --> T6
    T6[_compute_debit: SUM RowDetails cif_fc WHERE type=D AND no trade] --> T7
    T7[_compute_allotment: SUM AllotmentItems cif_fc WHERE no BOE] --> T8
    T8[_compute_trade: SUM LicenseTradeLine cif_fc WHERE SALE] --> T9

    T9[raw = credit - debit - allotment - trade] --> T10
    T10[balance = max 0 raw quantize 2dp ROUND_DOWN] --> T11

    T11[LicenseBalance.update_or_create balance_cif=balance] --> T12
    T12{balance < 500?}
    T12 -- Yes --> T13[is_null=True]
    T12 -- No --> T14[is_null=False]
    T13 --> T15
    T14 --> T15

    T15{expiry_date < today?}
    T15 -- Yes --> T16[is_expired=True]
    T15 -- No --> T17[is_expired=False]
    T16 --> T18
    T17 --> T18

    T18[LicenseFlags.update_or_create is_null is_expired] --> T19
    T19[_update_item_level_balances license_id] --> T20

    T20[SELECT FOR UPDATE all import items WHERE license_id] --> T21
    T21[Bulk aggregate: debit_map and allot_map in 2 queries] --> T22
    T22[Compute avail_qty per item = max 0 qty-deb-allot] --> T23
    T23[Collect changed items] --> T24
    T24{Any items changed?}
    T24 -- Yes --> T25[bulk_update 5 fields in 1 query]
    T24 -- No --> T26
    T25 --> T26

    T26[COMMIT transaction] --> T27
    T27[Log INFO with all components and result] --> END[Task done; ACK message]
```

---

## Flow 4: Report Generation

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as Django API
    participant DB as PostgreSQL
    participant Redis as Redis
    participant Worker as Celery Worker

    User->>FE: Select licenses, format=PDF, click Generate
    FE->>API: POST /api/v1/reports/balance/generate/ {license_ids:[1,2,3], format:"pdf"}
    
    API->>API: BalanceReportRequestSerializer.is_valid()
    API->>API: task_id = uuid.uuid4()  ← PRE-GENERATE
    API->>DB: INSERT CeleryTaskTracker(task_id, status="PENDING")
    Note over DB: Tracker row exists BEFORE task dispatched
    API->>Redis: generate_balance_report_task.apply_async(task_id=task_id, kwargs={...})
    API-->>FE: 202 {task_id: "abc-123"}
    
    Note over FE: Starts polling
    FE->>API: GET /api/v1/reports/status/abc-123/
    API->>DB: SELECT status FROM core_celerytasktracker WHERE task_id="abc-123"
    API-->>FE: {status:"pending"}

    Redis-->>Worker: deliver task
    Worker->>DB: UPDATE CeleryTaskTracker SET status="STARTED"
    Worker->>DB: SELECT licenses, compute report...
    Worker->>Worker: Generate PDF/Excel file
    Worker->>DB: UPDATE CeleryTaskTracker SET status="SUCCESS", result_url="..."
    Worker->>Redis: ACK message

    FE->>API: GET /api/v1/reports/status/abc-123/
    API-->>FE: {status:"done", file_url:"..."}
    FE->>FE: Show download button
    User->>FE: Click Download
    FE->>API: GET /protected-media/reports/abc-123.pdf (blob)
    Note over API: X-Accel-Redirect header set
    API-->>FE: 200 (blob via nginx internal redirect)
```
