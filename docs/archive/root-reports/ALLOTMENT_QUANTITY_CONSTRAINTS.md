# Allotment Quantity Constraints — LOCKED SPECIFICATION

**Status:** FOUNDATIONAL INVARIANT (locked before Phase A.2)

**Applies to:** All allocation/planning operations

---

## Core Principle

Every allotment must enforce **TWO independent quantity constraints** that must both pass before any allocation is valid.

---

## Constraint 1: Per-Import-Item-Line Maximum

**Rule:**
```
For every Import Item line in the allotment:

  Allotted Quantity ≤ Current Available Quantity of that Import Item
```

**Meaning:**
The system must never allot more quantity to any single import-item line than that line currently has available.

**Example (VALID):**
```
Import Item 1
├─ Available Qty = 50
├─ Requested Allotment = 40
└─ Status: VALID (40 ≤ 50)
```

**Example (INVALID):**
```
Import Item 1
├─ Available Qty = 50
├─ Requested Allotment = 60
└─ Status: INVALID ❌ (60 > 50)

Maximum allowed = 50
```

**Timing:** The validation must use the **live available quantity**, rechecked at Save time, not a stale UI value.

---

## Constraint 2: Total Plan Quantity Maximum

**Rule:**
```
Total Planned Quantity ≤ Total Available Quantity

where:
  Total Available Qty = sum of current available quantities across all eligible import items
  Total Planned Qty = sum of all allotted quantities in the plan
```

**Meaning:**
The sum of all quantities allocated across all import-item lines in a single plan cannot exceed the sum of all available quantities.

**Example (VALID):**
```
Import Item 1 → Available = 50
Import Item 2 → Available = 30
Import Item 3 → Available = 20
─────────────────────────────
Total Available = 100

Allotment Plan:
├─ Item 1 Allotted = 30
├─ Item 2 Allotted = 25
├─ Item 3 Allotted = 15
└─ Total Allotted = 70

Status: VALID (70 ≤ 100)
```

**Example (INVALID):**
```
Import Item 1 → Available = 50
Import Item 2 → Available = 30
Import Item 3 → Available = 20
─────────────────────────────
Total Available = 100

Allotment Plan:
├─ Item 1 Allotted = 40
├─ Item 2 Allotted = 40
├─ Item 3 Allotted = 40
└─ Total Allotted = 120

Status: INVALID ❌ (120 > 100)
```

---

## BOTH Constraints Are Mandatory

**A plan is valid ONLY when BOTH conditions pass:**

```
Constraint 1 (per-line):
  For each import-item line i:
    planned_qty[i] ≤ available_qty[i]

AND

Constraint 2 (total):
  sum(planned_qty[i] for all i) ≤ sum(available_qty[i] for all i)
```

**Passing the total constraint does NOT override a line-level violation.**

### Critical Example: Line Constraint Overrides Total

```
Import Item 1 → Available = 20
Import Item 2 → Available = 80
─────────────────────────────
Total Available = 100

Allotment Plan:
├─ Item 1 Planned = 30   ← EXCEEDS line availability (30 > 20)
├─ Item 2 Planned = 50
└─ Total Planned = 80    ← Within total (80 ≤ 100)

Result: INVALID ❌

Reason: Item 1 line constraint fails.
The fact that the total is within budget does NOT make the plan valid.
```

**Correct Fix:**
```
Allotment Plan:
├─ Item 1 Planned = 20   ← Now respects line constraint
├─ Item 2 Planned = 50
└─ Total Planned = 70    ← Still within total

Result: VALID ✓
```

---

## Validation Implementation

### Where: Server-Side Only

These constraints must be enforced in the allocation validation service, never in the frontend.

The frontend may display constraints for user guidance, but the **authoritative validation happens at Save time on the server**.

### When: At Save Time

Before saving/committing any allotment:

1. **Recheck live availability** for every import-item line.
2. **Recalculate total available quantity** across all items.
3. **Recheck each line's planned quantity** against its current available.
4. **Recheck total planned quantity** against total available.
5. **Atomically validate both constraints** before persisting.

Do not rely on stale frontend calculations.

Do not allow stale availability to create an over-allocation.

---

## Allotment Display Model

The Allotment UI remains simple and is organized hierarchically:

```
Allotment
│
├── License 1
│   ├── License Details (Number, Date, Expiry, Port, Exporter, Status)
│   ├── [Planned Qty]
│   │
│   └── Import Item Lines
│       ├── Sr No
│       ├── Import Item Description
│       ├── Current Available Qty
│       └── Current Available CIF/Value
│
├── License 2
│   ├── License Details
│   ├── [Planned Qty]
│   └── Import Item Lines
│
└── License 3
    ├── License Details
    ├── [Planned Qty]
    └── Import Item Lines
```

License header displays:
- License Number
- License Date
- Expiry Date
- Port Code
- Notification
- Purchase Status
- Exporter Name

Followed by:
- **Planned Qty** (total for the license)
- Import Item lines with:
  - Serial Number
  - Item Description
  - Available Quantity (current, live)
  - Available CIF/Value (current, live)

---

## Automatic License Ordering

When the system automatically determines the license order for planning:

**Priority sequence (applied in order):**
1. **Earliest expiry date** (closest to today first)
2. **Earlier issue/acquisition date** (older licenses first)
3. **License number ascending** (lexicographic/numeric order)

**Applied before sorting:**
- **Allowed Expiry Date** is applied as a hard eligibility filter.
- Only licenses with `expiry_date >= allowed_expiry_date` are considered.
- Licenses without an expiry date or license number are excluded from automatic planning.

---

## Important Preservation Rules

- Do **not** redesign the existing Allotment Create or Allotment Action workflow if it is already correct.
- **Preserve** the current workflow and implement these constraints within the existing domain/service validation layer.
- These constraints are **financial invariants** and must be enforced **server-side**.
- Do **not** add these constraints as UI-only validation.

---

## Locked Status

**This specification is LOCKED and FOUNDATIONAL.**

- Do not reconsider or weaken these constraints.
- Both Constraint 1 and Constraint 2 are mandatory and independent.
- Do not allow Constraint 2 to override Constraint 1.
- Implement in Phase A.2 canonical validation services (before Phase A.3 atomicity/transactions).

---

**Status:** Ready for Phase A.2 implementation.

**Next:** Phase A.2 domain services will implement these constraints in the validation layer.
