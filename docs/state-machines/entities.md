# Entity State Machines

> **All entity state transitions with Mermaid diagrams.**

---

## 1. License State

Licenses don't have an explicit `status` field. Their "state" is derived from flag fields computed by `recompute_license_balance()`.

```mermaid
stateDiagram-v2
    [*] --> Active : License created + import items added + balance > 500

    Active --> NearExpiry : expiry_date within 30 days AND balance >= 100
    NearExpiry --> Active : expiry_date extended
    
    Active --> Null : balance_cif < 500
    Null --> Active : Additional export items added (credit increases)
    Null --> NearExpiry : expiry within 30 days
    
    Active --> Expired : license_expiry_date < today
    NearExpiry --> Expired : license_expiry_date < today
    Null --> Expired : license_expiry_date < today
    
    Expired --> Active : expiry_date updated (DGFT extension)
    
    note right of Active
        is_null=False
        is_expired=False
    end note
    
    note right of Null
        balance_cif < 500
        is_null=True
    end note
    
    note right of Expired
        is_expired=True
        regardless of balance
    end note
```

**Derived state logic** (from `balance_service.py`):
```python
is_null = balance_cif < Decimal("500")
is_expired = license_expiry_date is not None and license_expiry_date < today
```

**Dashboard display**:
- Active: `is_active=True AND is_expired=False AND is_null=False`
- Expired: `is_expired=True`
- Null (near zero): `is_null=True`
- Expiring: `is_active=True AND expiry within 30 days AND balance >= 100`

---

## 2. Allotment State

AllotmentModel has `is_boe` and `is_allotted` boolean flags, but the key state is determined by its relationship to a BOE.

```mermaid
stateDiagram-v2
    [*] --> Pending : Allotment created (bill_of_entry IS NULL)

    Pending --> LinkedToBOE : BillOfEntryModel.allotment.set() called
    LinkedToBOE --> Pending : BOE updated to remove allotment (M2M remove)
    LinkedToBOE --> Consumed : BOE fully processed (is_boe=True)
    
    Pending --> Cancelled : delete_allotment() called
    
    note right of Pending
        allotment.bill_of_entry IS NULL
        counts in _compute_allotment()
        reduces license balance
    end note
    
    note right of LinkedToBOE
        allotment.bill_of_entry IS NOT NULL
        exits _compute_allotment()
        BOE debit takes effect instead
    end note
    
    note right of Consumed
        is_boe=True
        AllotmentModel.is_allotted=True
    end note
```

**Balance impact by state**:
- `Pending`: AllotmentItems.cif_fc counted in allotment balance component
- `LinkedToBOE`: allotment exits formula; RowDetails debit enters formula
- `Cancelled`: allotment removed; LicenseItemPlan restored; balance recomputed

---

## 3. BOE RowDetails State

```mermaid
stateDiagram-v2
    [*] --> Active : RowDetails created (is_frozen=False, is_dispute=False)

    Active --> Frozen : Ledger upload marks row as frozen
    Active --> Disputed : Ledger upload flags row as missing
    Active --> Deleted : delete_row_detail() called

    Frozen --> Frozen : Cannot be edited (save() returns early)
    
    Disputed --> Resolved : resolve_dispute_row() OR resolve_dispute()
    Resolved --> Active : is_dispute cleared; sr_number linked
    
    Deleted --> [*]
    
    note right of Active
        Regular editable row
        Counts in _compute_debit()
    end note
    
    note right of Frozen
        is_frozen=True
        Set during ledger upload
        Cannot be modified via API
        Still counts in balance
    end note
    
    note right of Disputed
        is_dispute=True
        Highlighted in UI (red)
        Needs manual review
    end note
```

**When rows become frozen**: During ledger upload (`LedgerUploadView`), rows created from ICEGATE data are marked `is_frozen=True`. These represent authoritative external data.

**When rows become disputed**: If a row existed in the previous ledger but is missing from the current ledger upload, it gets `is_dispute=True`.

---

## 4. Task State Machine

```mermaid
stateDiagram-v2
    [*] --> PENDING : create_task() called

    PENDING --> IN_PROGRESS : (not implemented in new backend)
    PENDING --> COMPLETED : complete_task()
    PENDING --> REJECTED : reject_task(reason=required)
    
    REJECTED --> PENDING : reopen_task()
    COMPLETED --> PENDING : reopen_task()
    
    note right of PENDING
        Default state
        STATUS_PENDING = "pending"
    end note
    
    note right of REJECTED
        requires reason text
        mark_rejected(by_user, reason)
        reason stored on task
    end note
```

**Service functions** (`task_service.py`):
```python
create_task(data, user)        → Task(status=PENDING)
complete_task(task)            → task.mark_completed() → status=COMPLETED
reject_task(task, by_user, reason) → task.mark_rejected() → status=REJECTED
reopen_task(task)              → task.status=PENDING → save()
add_remark(task_id, text, user) → TaskRemark.create()
```

---

## 5. Celery Report Task State

```mermaid
stateDiagram-v2
    [*] --> PENDING : CeleryTaskTracker created (before apply_async!)
    
    PENDING --> STARTED : Worker picks up task (_mark_started)
    STARTED --> SUCCESS : Report generation complete
    STARTED --> FAILURE : Exception during generation (after 3 retries)
    STARTED --> RETRY : Retry in progress (max 2 retries)
    RETRY --> STARTED : Retry attempt
    
    SUCCESS --> [*]
    FAILURE --> [*]
    
    note right of PENDING
        Row created BEFORE apply_async
        Prevents tracker race condition
    end note
    
    note right of STARTED
        Worker ACKs message only after completion
        (acks_late=True)
    end note
```

**CeleryTaskTracker DB status values** (`core_celerytasktracker.status`):
- `"PENDING"` — queued, not started
- `"STARTED"` — worker processing
- `"SUCCESS"` — completed, file available
- `"FAILURE"` — failed after retries
- `"RETRY"` — retry in progress

**API poll**: `GET /api/v1/reports/status/{task_id}/`

---

## 6. Incentive License State (RODTEP/ROSTL/MEIS)

Simpler than advance licenses — tracked by `sold_status`:

```mermaid
stateDiagram-v2
    [*] --> NotSold : IncentiveLicense created (sold_status=NO)
    
    NotSold --> PartialSold : sold_value > 0 AND sold_value < license_value
    PartialSold --> FullySold : sold_value >= license_value
    
    FullySold --> PartialSold : Trade reversed
    PartialSold --> NotSold : All trades reversed
    
    note right of NotSold
        sold_status = "NO"
        balance_value = license_value
    end note
    
    note right of PartialSold
        sold_status = "PARTIAL"
        balance_value = license_value - sold_value
    end note
    
    note right of FullySold
        sold_status = "YES"
        balance_value = 0
    end note
```
