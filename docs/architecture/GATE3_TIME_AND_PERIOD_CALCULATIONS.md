# GATE 3: Time and Period Calculation Rules

**Status:** GATE 3 ARCHITECTURE DESIGN — Do NOT implement. For approval only.

**Purpose:** Define authoritative, deterministic rules for every time-dependent calculation so that the same license balance calculated on different dates produces consistent results.

---

## Date Semantics (Single Definitions)

### Transaction Date
- **Meaning:** When the business event occurred (import, BOE debit, etc.)
- **Authority:** Data entry (user or system import)
- **Immutable:** Yes (never changes after entry)
- **Timezone:** UTC (all transactions stored in UTC)
- **Example:** A BOE dated 2026-05-15 occurred on that date in India Standard Time (IST), but stored as UTC timestamp

### Created Date
- **Meaning:** When the record was first entered into the system
- **Authority:** Auto-populated at record creation
- **Immutable:** Yes
- **Used for:** Audit trail, not for calculation

### Posting Date
- **Meaning:** When a transaction's value takes effect (may differ from transaction date)
- **Authority:** Determined by business rules (e.g., BOE effective when debit is matched)
- **Immutable:** No (can be recalculated)
- **Used for:** Financial close, period accounting
- **Example:** BOE dated 2026-05-15 but posted 2026-05-20 for balance calculation

### Updated Date
- **Meaning:** When record was last modified
- **Authority:** Auto-updated on change
- **Immutable:** No
- **Used for:** Audit trail, cache invalidation

### Effective Date (Rates)
- **Meaning:** When a currency or pricing rate applies
- **Authority:** Data entry (master data)
- **Immutable:** Yes
- **Used for:** Rate selection for conversions
- **Window:** `[effective_from, effective_to]` inclusive

---

## Period Boundaries

### Standard Definition

```python
class LedgerPeriod:
    start_date: date          # Inclusive
    end_date: date            # Inclusive
    fiscal_period: str        # E.g., "Q1-2026", "FY-2025-26"
```

### Inclusivity Rules

**Both boundaries are INCLUSIVE:**

```python
# A period from 2026-01-01 to 2026-03-31 includes:
# - All transactions dated 2026-01-01
# - All transactions dated 2026-03-31
# - ALL transactions in between

start_date = date(2026, 1, 1)
end_date = date(2026, 3, 31)

# CORRECT: Use __gte and __lte
transactions = Transaction.objects.filter(
    date__gte=start_date,
    date__lte=end_date
)
```

### Timezone Handling

**Default Timezone:** UTC (all calculations are UTC-based)

```python
# CORRECT
from django.utils import timezone
from datetime import date

today_utc = timezone.now().date()  # Always UTC

# NOT this (local timezone may differ)
from datetime import datetime
today_local = datetime.now().date()  # ← Local timezone, incorrect
```

### Same-Day Transaction Ordering

**Transactions on the same date are ordered deterministically by:**

1. **Transaction ID (ascending)**
2. **Then by created timestamp (seconds precision)**

**Rule:** Never use creation timestamp alone (microseconds can vary on cloud systems). Always use (transaction_id, created_timestamp) tuple.

```python
# CORRECT: Deterministic ordering for same-day transactions
transactions = Transaction.objects.filter(
    date=target_date
).order_by("id", "created")  # ID first, then created timestamp

# WRONG: Using created timestamp alone (non-deterministic at microsecond precision)
transactions = Transaction.objects.filter(
    date=target_date
).order_by("created")  # ← Microseconds can vary
```

### Why This Matters

**Use case:** Computing running balance — if two BOE debits occur on 2026-05-15, which one reduces the balance first?

```python
# Scenario: License has 1000 balance, two BOEs on same date
# BOE-A: 600 (id=100)
# BOE-B: 500 (id=101)

# Correct (id-ordered):
balance_after_A = 1000 - 600 = 400  (BOE-A with id=100 goes first)
balance_after_B = 400 - 500 = -100  (BOE-B with id=101 goes second)
# Final: -100 (overused by 100)

# WRONG (unsorted or created-time ordered):
balance_after_B = 1000 - 500 = 500  (if BOE-B processed first)
balance_after_A = 500 - 600 = -100  (BOE-A goes second)
# Final: -100 (same value, but different intermediate state)
```

While the final value may be the same, the **running balance** at each step differs, which affects reports showing "balance after transaction X."

---

## Running Balance Calculation (PRIMARY P0 RULE)

### Definition

**License Running Balance:** Balance AFTER each transaction, in transaction-date order (primary) then transaction-id order (tiebreaker).

### Scope: License-Wide (NOT Per-Company)

**Rule:** Running balance is always license-wide atomic. Do NOT restart per company.

**Backend canonical implementation:**
```python
# CORRECT (license-wide)
balance = opening_balance
running_balances = []
for txn in transactions_ordered_by_date_then_id:
    if txn.type == "PURCHASE":
        balance += txn.amount
    elif txn.type == "SALE":
        balance -= txn.amount
    elif txn.type == "COMMISSION":
        balance -= txn.amount  # ← Commissions reduce balance
    running_balances.append((txn.id, balance))
```

### Ordering: By Date First, Then ID

```python
def get_ledger_transactions(license_id: int) -> List[Transaction]:
    """Get transactions in ledger order: date (asc), then id (asc)."""
    return Transaction.objects.filter(
        license_id=license_id
    ).order_by("date", "id")
```

### Commission Treatment

**BUSINESS DECISION GATE 3B:** Does COMMISSION_SALE reduce the running balance?

Currently:
- **Backend (ledger_pdf.py):** YES, commissions are debits
- **Frontend (LicenseLedgerDetail.tsx):** NO, commissions are excluded

**Gate 3 Status:** Unresolved. See LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md §10 (B4).

For now, code defensively:
```python
COMMISSION_INCLUDED_IN_BALANCE = True  # ← Single source of truth

def calculate_balance_impact(txn):
    if txn.type == "COMMISSION_SALE":
        if COMMISSION_INCLUDED_IN_BALANCE:
            return -txn.amount  # Debit
        else:
            return Decimal("0")  # No impact
```

---

## Period Types (License Fiscal vs. Other)

### License Fiscal Year
- **Defined by:** LicenseDetailsModel.issue_date and expiry_date
- **Authority:** License master data (when license was granted)
- **Used for:** License-specific balance close
- **Example:** License issued 2025-06-01, expires 2026-05-31 → Fiscal year is 2025-06-01 to 2026-05-31

### SION Norm Period
- **Defined by:** SionNormClass regulations
- **Authority:** DGFT regulatory data
- **Used for:** Norm-specific plan percentage (may differ from license period)
- **Example:** E5 norm has a specific planning horizon unrelated to license expiry

### Reporting Period
- **Defined by:** Report parameters (start_date, end_date filters)
- **Authority:** User selection or system default (FY, quarter, month)
- **Used for:** Filtered reports
- **Example:** "Show me all transactions from 2026-01-01 to 2026-03-31"

### Fiscal Close
- **Meaning:** End of a financial reporting period
- **Authority:** Company accounting rules (e.g., fiscal year ends 2026-03-31)
- **Used for:** Period-end balance snapshots
- **Rule:** Balance calculated at end of day on fiscal close date (including that day's transactions)

---

## Running Balance Determinism (Test Rule)

**GOLDEN DATASET REQUIREMENT:** Same license, same filters, calculated on different system dates must produce identical results.

```python
# Example test
def test_running_balance_deterministic():
    """Running balance must be identical regardless of calculation date."""
    license_id = 123
    
    # Calculate on day 1
    balance_day1 = LicenseBalanceCalculator.calculate_financial_balance_for_licenses([license_id])
    
    # ... time passes, new unrelated data is added to other licenses ...
    
    # Calculate on day 2
    balance_day2 = LicenseBalanceCalculator.calculate_financial_balance_for_licenses([license_id])
    
    # Must be identical
    assert balance_day1[license_id] == balance_day2[license_id]
```

### Why Determinism Is Critical

- Reports must show the same Balance column value every time they're downloaded
- Audit trail requires reproducible calculations
- Reconciliation depends on deterministic values

---

## Historical Rate Selection (Exchange Rates)

### Rule: Select Rate Based on Transaction Date

Not calculation date.

```python
def apply_historical_rate(transaction, base_amount: Decimal) -> Decimal:
    """Apply exchange rate effective on transaction date."""
    rate = ExchangeRateModel.objects.filter(
        from_currency="USD",
        to_currency="INR",
        effective_from__lte=transaction.date,    # ← txn date
        effective_to__gte=transaction.date
    ).first()
    
    if not rate:
        raise ValueError(f"No rate for {transaction.date}")
    
    return quantize_2dp(base_amount * rate.rate)

# WRONG: Using today's rate instead of historical
today_rate = ExchangeRateModel.objects.latest("created")  # ← WRONG
amount_inr = base_amount * today_rate.rate
```

### Handling Missing Historical Rates

If a transaction date has no rate:

```python
# Option 1: Use most recent rate before that date
rate = ExchangeRateModel.objects.filter(
    effective_to__gte=transaction.date
).order_by("-effective_from").first()

# Option 2: Reject and flag for manual entry
if not rate:
    raise ValueError(f"Rate missing for {transaction.date}; needs manual entry")

# DO NOT invent rates
```

---

## Comparison Across Periods

### Rule: Normalize by Period Boundary

When comparing balances across periods, use the same date boundaries:

```python
# CORRECT: Same period boundaries
period1 = (date(2026, 1, 1), date(2026, 3, 31))
period2 = (date(2025, 1, 1), date(2025, 3, 31))

balance_2026_q1 = calculate_period_balance(license, *period1)
balance_2025_q1 = calculate_period_balance(license, *period2)

# Now comparison is apples-to-apples

# WRONG: Comparing different period lengths
balance_2026_jan = ...  # 2026-01-01 to 2026-01-31 (31 days)
balance_2025_feb = ...  # 2025-02-01 to 2025-02-28 (28 days)
# ← Comparison is invalid (different lengths)
```

---

## Rollback / Recalculation After Corrections

### Scenario: BOE date is corrected (e.g., data entry error discovered)

When a transaction's date changes:

1. **Audit log** the old and new dates
2. **Recalculate running balance** for all subsequent transactions (they're ordered by date)
3. **Regenerate reports** if they were affected
4. **Mark affected snapshots** (period-end balances) as stale

```python
def correct_transaction_date(transaction, new_date: date):
    """Correct a transaction's date, recalculating all downstream balances."""
    old_date = transaction.date
    transaction.date = new_date
    transaction.save()
    
    # Log the change
    AuditLog.objects.create(
        action="DATE_CORRECTED",
        transaction_id=transaction.id,
        old_value=old_date,
        new_value=new_date
    )
    
    # Invalidate cached balances for this license
    invalidate_balance_cache(transaction.license_id)
    
    # Regenerate reports if needed
    # (set a flag for async regeneration)
```

---

## Period-End Balance Snapshot

### Purpose
Capture the balance at the end of a period (e.g., quarter-end for audit).

### Calculation
```python
def get_period_end_balance(license_id: int, end_date: date) -> Decimal:
    """Balance after all transactions on or before end_date."""
    transactions = Transaction.objects.filter(
        license_id=license_id,
        date__lte=end_date  # ← Include end_date
    ).order_by("date", "id")
    
    balance = calculate_running_balance(transactions)
    return balance
```

### Storage (if needed)
```python
class PeriodEndSnapshot:
    license = ForeignKey(License)
    period_end_date = DateField()
    balance_at_end = DecimalField()
    calculated_at = DateTimeField(auto_now=True)
    # If recalculated later, old snapshot is archived, not deleted
```

---

## Comparison with Frontend (P0 DEFECT)

### Current Discrepancy

| Aspect | Backend | Frontend |
|--------|---------|----------|
| Scope | License-wide | Per-company |
| Date Order | By date, then id | N/A (type-ordered) |
| Commission | DEBIT | EXCLUDED |
| Restart | Never | Per company |

### Resolution Path (Gate 3 Business Decision)

See LEDGER_DETAIL_DISPLAY_DATASET_DESIGN.md §10 (B2):

**B2: Running Balance Convention** — Is backend's license-wide convention correct, or should it be per-company like the frontend?

Currently blocking Phase 3B (Ledger Detail implementation). Business decision required.

---

## Migration Checklist (for Gate 4)

Before any time-dependent calculation goes live:

- [ ] Date semantics defined (transaction date, posting date, effective date)
- [ ] Period boundaries documented (inclusive/exclusive)
- [ ] Timezone default set (UTC)
- [ ] Same-day ordering deterministic (id, then timestamp)
- [ ] Running balance rule tested for determinism
- [ ] Historical rates selected by txn date, not calc date
- [ ] Rollback/recalculation path documented
- [ ] Period-end snapshots handled correctly
- [ ] Audit logging for date corrections
- [ ] Test coverage: same-day multiple txns, missing rates, date changes

---

## Version and Status

- **Version 1.0** — Gate 3 Architecture Design, 2026-08-10
- **Updated by:** Solutions Architect
- **Compliance:** Mandatory for all time-dependent calculations
- **Blocking Issue:** B2 (running balance convention) requires business decision
- **Next Update:** Post-approval, Phase 3B (gate 3 business decision)
