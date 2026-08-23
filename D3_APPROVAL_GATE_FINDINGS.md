# D3 FINDINGS: Approval Gate

## Current Approval Model

**Field:** AllotmentModel.is_approved (boolean, default=False)

**Type:** Explicit approval flag on the allotment itself (not a workflow state).

---

## Current Enforcement

**Where is_approved is checked:**

1. **license_overview_allotments.py** (Req 4-5)
```python
if allotment.is_approved:
    # Include in overview
```

2. **views_export.py** (display)
```python
'is_approved': allotment.is_approved  # Exported in CSV/XLSX
'is_approved': '✓' if allotment.is_approved else ''  # Display
```

3. **Serializer** (included in API response)
```python
fields = [..., 'is_approved', ...]
```

4. **Admin inline_editable**
```python
inline_editable = ['is_approved']  # Can toggle in admin
```

**Where is_approved is NOT checked:**

- **allocate_items endpoint** (allocation creation) — NO CHECK
- **AllotmentViewSet** — NO CHECK (create/update/delete all allowed without approval)
- **Any API authorization** — NO CHECK

**Finding:** is_approved is **informational/filterable** but does **NOT gate allocation operations**. The field can be toggled, but it doesn't control whether allocation is permitted.

---

## Current Lifecycle

1. Allotment created (is_approved = False)
2. User can toggle is_approved to True/False in admin or API
3. When is_approved = True: shown in license overview, marked in exports
4. No state transition rules; can toggle at any time

**Finding:** No formal approval workflow. It's just a flag that can be toggled anytime.

---

## Affected Operations

**Currently allowed regardless of is_approved:**
- Create allocation
- Update allocation
- Delete allocation
- Release allocation
- Create BOE from allotment
- Finalize BOE
- Any other mutation

**Only filtered/displayed by is_approved:**
- License overview (shows only approved allotments)
- Export CSV/XLSX (marks approved status)

---

## Required Behavior (from Spec)

Specification Req 3, D3 asks: "Should allocation require is_approved?"

**Not explicitly stated in the 49 requirements.**

The specification focuses on:
- Manual allocations (Req 5) — no mention of approval
- Automatic planning (Req 22) — no mention of approval
- BOE protection (Req 14) — no mention of approval
- Release/reactivation (Req 8-10) — no mention of approval

**Inference:** Approval gate is NOT required by the spec. It's optional business logic.

---

## Risk

**If we implement approval gate:**
- All existing allocations created while is_approved=False would become invalid
- Would need migration to set is_approved=True on all existing allotments
- Or clear is_approved history

**If we leave it as-is:**
- is_approved is just metadata/filtering
- Doesn't block allocation
- No risk to existing functionality

---

## Recommendation for Phase A

**Status: OPTIONAL GATE**

1. **Do NOT gate allocation on is_approved in Phase A**
   - Specification doesn't require it
   - Current system doesn't enforce it
   - Would break backward compatibility

2. **Keep is_approved as informational/filterable**
   - User can toggle it
   - Shows in exports and overviews
   - No operational impact

3. **IF business decides it should gate allocation:**
   - Can add in a later phase
   - Would check: if not allotment.is_approved, raise error in allocate_items
   - Migration to backfill all existing as approved

**No code changes required for D3 in Phase A.**

**Business decision:** Is approval required before allocation, or is it just informational?
