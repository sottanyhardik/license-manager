# Dashboard Redesign — PHASE 1: Current State Audit

**Date:** 2026-09-25  
**Status:** Complete  
**Scope:** Frontend Dashboard component analysis and operational redesign planning

---

## Executive Summary

The current Dashboard is functionally complete but designed as a generic analytics dashboard rather than an **operational control center**. This audit identifies structural, informational, and visual improvements needed to make License Manager operations transparent, scannable, and action-focused.

**Key Finding:** The Dashboard must answer **"What do I need to do right now?"** first, then provide context. Currently, it presents equal weight to all metrics.

---

## 1. Current Dashboard Structure

### File Location
- **Primary:** `frontend/src/pages/Dashboard.tsx` (289 lines)
- **Related:** 
  - `frontend/src/pages/Dashboard.test.tsx`
  - `frontend/src/pages/Dashboard.contract.test.tsx`
  - `frontend/src/pages/dashboardContract.ts`

### Current Sections (Top to Bottom)

#### 1.1 Page Header
```
Pretitle: "Home"
Title: "Dashboard"
Description: Current date + last refresh time
Actions: Refresh btn, New Allotment btn, New BOE btn
```
- **Current state:** Clear but minimal
- **Issue:** No indication of urgency or system health

#### 1.2 License Health (5 Stats)
```
Cards: Total | Active | Expired | Missing DGFT | Expiring soon
Layout: Responsive grid (2 col mobile, 3 col tablet, 5 col desktop)
```
- **Current state:** Functional, compact
- **Issue:** Treats "Expiring soon" as equal to "Total"—wrong priority

#### 1.3 Operational Activity (3 Stats)
```
Cards: Allotments | Bills of Entry | Pending Invoices
Layout: 2 col mobile, 3 col desktop
```
- **Current state:** Duplicates BOE data (mentioned in both sections)
- **Issue:** Allotments section feels disconnected from the primary BOE flow

#### 1.4 Attention Required Card (Complex)
```
Left (5 cols on desktop):
  - Tab system: "Expiring soon" (default) | "Missing DGFT" | "Pending invoices"
  - Expiring soon tab: Table with sortable rows (License # | Expiry | Balance | Status)
  - Missing DGFT tab: Empty state with "Review queue" button
  - Pending invoices tab: Empty state with "Review queue" button
```
- **Current state:** Compact, keyboard-navigable
- **Issue:** Tab system confusing—users need to click through to see what needs attention

#### 1.5 BOE Monthly Trend Chart
```
Right (3 cols on desktop):
  - Bar chart: BOE count by month (last 3 months)
  - Details: Expandable table below chart
```
- **Current state:** Visual, nice polish
- **Issue:** Rarely needed on first visit; takes up prime real estate

#### 1.6 Recent Bills of Entry Table
```
Right (4 cols on desktop):
  - Columns: BOE #, Date, Importer
  - Scrollable, click-through to edit
```
- **Current state:** Clean, scannable
- **Issue:** No indication of which are invoiced/pending

#### 1.7 Recent Allotments Table
```
Full width:
  - Columns: Date | Item Name | Quantity | CIF FC
  - Scrollable, click-through to allocate
```
- **Current state:** Functional
- **Issue:** Why is allotments last if they're a primary operational flow?

---

## 2. Current Data Flow & Permissions

### API Call
- **Single endpoint:** `GET /dashboard/`
- **Response shape:**
  ```javascript
  {
    license_stats: { total, active, expired, null_dfia, expiring_soon },
    allotment_stats: { total, recent[] },
    boe_stats: { total, pending_invoices, recent[] },
    expiring_licenses: [{ license_number, expiry_date, balance_cif, days_to_expiry }, ...],
    boe_monthly_trend: [{ month, label, count, value }, ...]
  }
  ```

### Permissions Checked
- `isSuperAdmin()`
- `hasAnyRole()` with specific role lists:
  - **Licenses:** LICENSE_MANAGER, LICENSE_VIEWER, TRADE_MANAGER, TRADE_VIEWER, REPORT_VIEWER
  - **Allotments:** ALLOTMENT_MANAGER, ALLOTMENT_VIEWER, REPORT_VIEWER
  - **BOE:** BOE_MANAGER, BOE_VIEWER, ACCOUNT_ACCESS, TL_GENERATE, REPORT_VIEWER

### State Management
- **Loading, refreshing, error states** — clear
- **Skeleton loaders** — present but minimal
- **Last updated** — tracked and displayed
- **Manual refresh** — implemented with spinner

---

## 3. Design System Readiness

### Available Components ✅

| Component | Status | Notes |
|-----------|--------|-------|
| **Button** | Ready | Variants: default, destructive, outline, secondary, ghost, link. Sizes: default, sm, lg, icon. |
| **Card/CardHeader/CardContent** | Ready | Full suite with border-b/border-t support. |
| **StatCard** | Ready | Compact + default modes. Tone system (primary, success, danger, warning, info, neutral). |
| **PageHeader** | Ready | Pretitle/title/description/actions standard. |
| **Badge** | Ready | Multiple variants available. |
| **EmptyState** | Ready | Sizes: default, page. Full icon/title/description/action. |
| **Icons** | Ready | lucide-react only. No legacy Bootstrap icons. |
| **Table** | Ready | Not shadcn—custom with DataTable component. |

### Design Tokens ✅
- **Theme variables:** CSS custom properties in `theme/tabler.css`
- **TONE_MAP, CHIP_TONE_MAP, ACTION_TONE_MAP** — all defined in `theme/tokens.js`
- **Spacing, radius, font scales** — available
- **Dark mode support** — built into design system

---

## 4. Current Issues & Pain Points

### Information Hierarchy Problems
1. **No clear "do this first" guidance** — All sections equally weighted
2. **Expiring licenses buried in tabs** — Key operational alert is obscured
3. **Missing DGFT count shown twice** — In both health metrics and attention tabs
4. **Pending invoices isolated** — Feels disconnected from BOE workflow

### Operational Flow Problems
1. **Chart takes time to load, low value** — BOE monthly trend is decorative
2. **Recent tables are long** — Requires scrolling even on desktop
3. **No status at a glance** — Users must interpret metrics mentally
4. **No "green light" indicator** — All clear ≠ good state

### Accessibility & UX Problems
1. **Tab system not discoverable** — Users may miss missing DGFT/pending invoices
2. **Dense tables** — Hard to scan, no visual rhythm
3. **Row navigation via tabIndex** — Works but not obvious
4. **Date formatting inconsistent** — Some use `displayDate()`, some raw

### Code Quality Issues
1. **Single component, 289 lines** — Could decompose sections
2. **Inline utility functions** — `displayDate`, `displayMoney`, `displayQuantity`, `parseDashboardDate`
3. **Unused imports** — `BarChart3` icon declared but not used
4. **Magic numbers** — 30-day expiry window hardcoded

---

## 5. Recommended Redesign Principles

### Operational Focus (NOT Analytics)
- **First impression:** "What's broken?" then "What's coming up?" then "How much do I have?"
- **Priority order:** Urgent alerts → Recent activity → Summary metrics
- **Eliminate decorative elements** — Every component must serve operational decision-making

### Information Hierarchy
1. **Red zone (Top):** Expiring soon (< 7 days), Missing DGFT, Failed operations
2. **Yellow zone (Upper-middle):** Expiring soon (7-30 days), Pending actions, Allotments at threshold
3. **Green zone (Lower):** Recent activity, Trends, Historical data

### KPI Presentation (Compact, Not Oversized)
- **Metric + label + subtitle** — 3 lines max
- **Icon (functional, not decorative)** — Identifies metric type
- **Status indicator if applicable** — Green/yellow/red dot or badge
- **No giant gradients or shadows** — Reduce visual noise

### Scanability
- **One column per key metric** — Avoid information overload
- **Status badges on every actionable item** — "Pending", "Active", "Resolved"
- **Color coding by urgency** — Red (< 7 days), Yellow (7-30 days), Green (safe)
- **No modal/tab hops required** — All urgent items visible at once

---

## 6. Proposed Information Architecture

### New Dashboard Grid Layout (Desktop)

```
[Page Header: Dashboard | Today | Refresh | Actions]

[URGENT ALERTS - Red Zone]
  Expiring soon (< 7 days): [X] | [View all →]
  Missing DGFT: [X] | [View all →]
  Pending Invoices: [X] | [View all →]

[KPI SUMMARY - Yellow/Green Zone - 4 columns]
  Active Licenses | Expired | Allotments | BOE Total
  [Number]       | [Number]| [Number]   | [Number]

[ATTENTION QUEUE - Full width, one tab removes need for clicking]
  Table: Licenses expiring in 30 days (Date | License | Balance | Days | Status)

[ACTIVITY DASHBOARD - 2 columns]
  Left: Recent BOE entries (Date | BOE # | Importer | Status)
  Right: Recent Allotments (Date | Item | Qty | Value | Status)

[OPERATIONAL METRICS - Optional]
  Monthly BOE trend (compact chart) | Allotment summary
```

### Data Model (Same backend endpoint, reframed frontend)

No backend changes needed. Frontend reorganizes existing data:

```javascript
URGENT = {
  expiring_soon: stats.licenses.expiring_soon,
  missing_dgft: stats.licenses.null_dfia,
  pending_invoices: stats.boe.pending_invoices,
  failed_operations: 0  // New: fetch separately if needed
}

SUMMARY = {
  active: stats.licenses.active,
  expired: stats.licenses.expired,
  allotments: stats.allotments.total,
  boe: stats.boe.total
}

ACTIVITY = {
  expiring_licenses,
  recent_boe: stats.boe.recent,
  recent_allotments: stats.allotments.recent
}
```

---

## 7. Design System Application Plan

### Phase 2 Component Mapping

| Section | Component | Variant | Notes |
|---------|-----------|---------|-------|
| **Header** | PageHeader | default | Existing, no change |
| **Alerts** | StatCard | compact, tone=danger/warning | 3 cards in row |
| **KPIs** | StatCard | compact, tone varies | 4 cards in row |
| **Expiring table** | DataTable | custom | Sort by days_to_expiry DESC |
| **Activity tables** | DataTable | custom | Compact styling |
| **Empty states** | EmptyState | default | When no data in section |
| **Buttons** | Button | outline/default | Nav buttons in tables |
| **Badges** | Badge | tone system | Status badges on rows |

### Color/Tone Mapping
- **Expiring (< 7 days):** tone="danger" → danger red, destructive text
- **Expiring (7-30 days):** tone="warning" → warning amber, warning text
- **Missing DGFT:** tone="danger" → critical, needs attention
- **Pending invoices:** tone="warning" → action required
- **Active:** tone="success" → healthy
- **Summary metrics:** tone="primary" → neutral information

---

## 8. Blast Radius Analysis

### Components & Services Modified

| File | Current Dependents | Risk | Notes |
|------|-------------------|------|-------|
| `Dashboard.tsx` | 3 (tests + routes) | Low | Changes isolated to page component |
| API call | Dashboard only | Low | No endpoint changes |
| StatCard | 53 files | Medium | DO NOT BREAK prop interface |
| Button | 53 files | Medium | DO NOT BREAK variants/sizes |
| Card | 31 files | Medium | DO NOT BREAK slot/styling |
| PageHeader | 20 files | Medium | DO NOT BREAK pretitle/title/description |

### Action Items
- ✅ Keep all public props on StatCard unchanged
- ✅ Don't add new Button variants (use existing ones)
- ✅ Don't modify Card structure (only adjust usage)
- ✅ PageHeader API stays same

---

## 9. Acceptance Criteria (Audit Phase)

- [x] Read current Dashboard.tsx
- [x] Understand backend data flow
- [x] Map existing permissions
- [x] Audit current UX issues
- [x] Verify design system readiness
- [x] Plan information architecture
- [x] Identify blast radius
- [x] Document current technical debt
- [x] Propose redesign principles

**Audit Status:** ✅ Complete. Ready for PHASE 2 implementation.

---

## 10. Next Steps (PHASE 2 Brief)

1. **Implement operational KPI section** — Compact cards, clear colors, scannable
2. **Reorganize attention flow** — Urgent first, no tabs required
3. **Streamline tables** — Remove decorative chart, add status indicators
4. **Apply design system** — Use Button, Card, StatCard, PageHeader as specified
5. **Maintain dark mode** — Test both themes throughout
6. **Verify accessibility** — Keyboard nav, color contrast, ARIA labels

---

## Appendix: Current Code Issues

### Unused Imports
```javascript
// Line 4: BarChart3 icon imported but never used
BarChart3, // ← Remove in Phase 2
```

### Magic Numbers
```javascript
// Line 72: 30-day window hardcoded
const goExpiringSoon = ... 30 * 864e5 // ← Extract to constant

// Line 28 (SkeletonStat): Hardcoded height
min-h-[76px] // ← Should match StatCard height
```

### Inline Utilities (Candidate for extraction to `/utils`)
```javascript
displayDate()        // ← Move to utils/dashboardDate.ts
displayMoney()       // ← Move to utils/formatters.ts
displayQuantity()    // ← Move to utils/formatters.ts
parseDashboardDate() // ← Already in utils/dashboardDate.ts
```

### Component Size
- **Current:** 289 lines (Dashboard.tsx)
- **Recommendation:** Decompose into:
  - `DashboardHeader.tsx` (PageHeader + actions)
  - `LicenseHealthSection.tsx` (5 stats)
  - `OperationalActivitySection.tsx` (3 stats)
  - `AttentionQueue.tsx` (Expiring/Missing/Pending)
  - `RecentActivityGrid.tsx` (Tables)
  - **Total expected:** ~50 lines each, easier to maintain

---

**End of Audit — PHASE 1 Complete**
