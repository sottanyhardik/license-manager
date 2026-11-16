# Dashboard Redesign — VISUAL SPECIFICATION

**Phase:** 2 (Implementation)  
**Status:** Specification ready  
**Last updated:** 2026-09-25

---

## 1. New Dashboard Grid Architecture

### Desktop Layout (1280px+)

```
┌─────────────────────────────────────────────────────────────────────┐
│  HOME > DASHBOARD                                    [↻ Refresh] [+] [+]  │
│  Today: Monday 25 September 2026 • Updated 14:32                      │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ URGENT ALERTS — ACTION REQUIRED                                        │
├──────────────────┬──────────────────┬──────────────────────────────────┤
│ Expiring soon    │ Missing DGFT     │ Pending invoices                 │
│ < 7 days: [12]   │ Records: [8]     │ Count: [5]                       │
│ [View all →]     │ [View all →]     │ [View all →]                     │
└──────────────────┴──────────────────┴──────────────────────────────────┘

┌─────────────────┬──────────────────┬─────────────┬────────────────────┐
│ SNAPSHOT — License Health              Operational Load               │
├─────────────────┼──────────────────┼─────────────┼────────────────────┤
│ Active: [234]   │ Expired: [12]    │ Allotments  │ BOE Entries        │
│                 │                  │ [156]       │ [89]               │
└─────────────────┴──────────────────┴─────────────┴────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ EXPIRING SOON — Next 30 Days (12 records)                              │
│                                                                          │
│ License   │ Expiry Date │ Balance (CIF) │ Days remaining │ Status      │
│───────────┼─────────────┼───────────────┼────────────────┼─────────────│
│ LIC-00123 │ 01 Oct 2026 │ $45,234.50    │ 6 days         │ 🔴 URGENT   │
│ LIC-00456 │ 05 Oct 2026 │ $12,000.00    │ 10 days        │ 🟡 SOON     │
│ LIC-00789 │ 15 Oct 2026 │ $89,999.99    │ 20 days        │ ⚪ MONITOR  │
│ [→ 9 more] ...                                                        │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────┬──────────────────────────────────┐
│ RECENT BOE ENTRIES (View all)        │ RECENT ALLOTMENTS (View all)     │
├──────────────────────────────────────┼──────────────────────────────────┤
│ Date        │ BOE #      │ Importer   │ Date       │ Item       │ Value  │
│─────────────┼────────────┼────────────┼────────────┼────────────┼────────│
│ 24 Sep 2026 │ BOE-26001  │ ACME Inc   │ 24 Sep     │ Vegatable  │ $5.2M  │
│ 23 Sep 2026 │ BOE-26000  │ Global Exp │ 23 Sep     │ Oil Palm   │ $3.1M  │
│ 22 Sep 2026 │ BOE-25999  │ Trade Co   │ 21 Sep     │ Chemicals  │ $8.9M  │
│                                        │                                 │
│ [Click row to continue...]             │ [Click row to continue...]     │
└──────────────────────────────────────┴──────────────────────────────────┘
```

### Tablet Layout (720px–1024px)

```
┌─────────────────────────────────────────────────┐
│  DASHBOARD                           [↻] [+] [+] │
│  Today: Mon 25 Sep • Updated 14:32               │
└─────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│ URGENT ALERTS                                    │
├──────────────────┬──────────────────┬────────────┤
│ Expiring < 7d    │ Missing DGFT     │ Pending    │
│ [12]             │ [8]              │ [5]        │
│ [View all]       │ [View all]       │ [View all] │
└──────────────────┴──────────────────┴────────────┘

┌──────────────┬──────────────┬──────────────┬────────────┐
│ Active: [234]│ Expired: [12]│ Allotments   │ BOE: [89]  │
│              │              │ [156]        │            │
└──────────────┴──────────────┴──────────────┴────────────┘

┌──────────────────────────────────────────────────┐
│ EXPIRING SOON (12 records)                       │
│ License │ Expiry │ Balance │ Days │ Status       │
│─────────┼────────┼─────────┼──────┼──────────────│
│ LIC-123 │ 01 Oct │ $45.2K  │ 6d   │ 🔴 URGENT    │
│ LIC-456 │ 05 Oct │ $12.0K  │ 10d  │ 🟡 SOON      │
│ [→ 10 more...]                                  │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│ RECENT BOE (View all)                            │
│ Date │ BOE # │ Importer │ Details                │
├──────┼───────┼──────────┼────────────────────────┤
│ 24S  │ 26001 │ ACME Inc │ [→]                    │
│ 23S  │ 26000 │ Global   │ [→]                    │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│ RECENT ALLOTMENTS (View all)                     │
│ Date │ Item │ Qty │ Value │ Details              │
├──────┼──────┼─────┼───────┼──────────────────────┤
│ 24S  │ Veg  │ 500 │ $5.2M │ [→]                  │
│ 23S  │ Oil  │ 200 │ $3.1M │ [→]                  │
└──────────────────────────────────────────────────┘
```

### Mobile Layout (< 720px)

```
┌──────────────────────────────┐
│ DASHBOARD       [↻] [+] [+]  │
│ Mon 25 Sep • 14:32           │
└──────────────────────────────┘

┌──────────────────────────────┐
│ URGENT: Expiring < 7 days    │
│ 12 licenses                  │
│ [View →]                     │
├──────────────────────────────┤
│ URGENT: Missing DGFT         │
│ 8 licenses                   │
│ [View →]                     │
├──────────────────────────────┤
│ URGENT: Pending invoices     │
│ 5 invoices                   │
│ [View →]                     │
└──────────────────────────────┘

┌──────────────────────────────┐
│ Snapshot                     │
├──────────────────────────────┤
│ Active: 234                  │
│ Expired: 12                  │
│ Allotments: 156              │
│ BOE: 89                      │
└──────────────────────────────┘

┌──────────────────────────────┐
│ Expiring Soon (swipeable)    │
│ License    │ Expires  │ Days │
│ LIC-123    │ 01 Oct   │ 6d   │
│ LIC-456    │ 05 Oct   │ 10d  │
│ [scroll →] ...              │
└──────────────────────────────┘

┌──────────────────────────────┐
│ Recent BOE [View all]        │
│ BOE-26001 │ ACME Inc         │
│ 24 Sep 26 │ [→]              │
├──────────────────────────────┤
│ BOE-26000 │ Global Exp       │
│ 23 Sep 26 │ [→]              │
└──────────────────────────────┘

┌──────────────────────────────┐
│ Recent Allotments [View all] │
│ Vegetable Oil │ $5.2M        │
│ 24 Sep        │ [→]          │
├──────────────────────────────┤
│ Oil Palm      │ $3.1M        │
│ 23 Sep        │ [→]          │
└──────────────────────────────┘
```

---

## 2. Component Specifications

### 2.1 URGENT ALERTS Section

**Purpose:** Immediately signal action required  
**Location:** Top, below PageHeader  
**Height:** ~100px  
**Visibility:** Always visible (no scrolling required on 1024px+)

#### Card Layout (Each Alert)
```
┌─────────────────────────────────┐
│ 🔴 EXPIRING SOON (< 7 DAYS)     │
│                                 │
│ 12 licenses in critical window  │
│                                 │
│          [View all →]           │
└─────────────────────────────────┘
```

**Component Stack:**
- **Wrapper:** `div` with responsive grid (3 cols desktop, 2 cols tablet, 1 col mobile)
- **Each card:** Custom card, NOT StatCard (StatCard is for metrics, not alerts)
- **Icon:** Lucide icon (AlertTriangle, Clock, Inbox depending on type)
- **Tone:** danger/warning/info (match severity)
- **Button:** outline variant, size="sm"

**Design Details:**
- Background: `bg-{tone}/5` (e.g., `bg-danger/5`)
- Border: `border-{tone}/30`
- Icon container: Size 24x24, `text-{tone}`
- Text: Bold count, regular description, muted action text
- Hover state: Slight lift, border becomes opaque

**Example Code Structure:**
```tsx
<div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
  {/* Expiring < 7 days card */}
  <AlertCard
    icon={AlertTriangle}
    title="Expiring soon (< 7 days)"
    count={stats.licenses.expiring_soon}
    description="Critical licenses"
    tone="danger"
    onViewAll={() => navigate("/licenses?...")}
  />
  
  {/* Missing DGFT card */}
  <AlertCard
    icon={FileX}
    title="Missing DGFT"
    count={stats.licenses.null_dfia}
    description="Require data entry"
    tone="danger"
    onViewAll={() => navigate("/licenses?...")}
  />
  
  {/* Pending invoices card */}
  <AlertCard
    icon={FileSpreadsheet}
    title="Pending invoices"
    count={stats.boe.pending_invoices}
    description="Awaiting follow-up"
    tone="warning"
    onViewAll={() => navigate("/bill-of-entries?...")}
  />
</div>
```

---

### 2.2 SNAPSHOT Section (KPIs)

**Purpose:** Provide quick operational metrics  
**Location:** Below alerts  
**Layout:** 4-column grid (desktop), 2-column (tablet), 1-column (mobile)  
**Component:** StatCard in compact mode

#### StatCard Specifications

**Props:**
```tsx
<StatCard
  compact={true}  // CRITICAL: Must be true for all dashboard cards
  label="Active licenses"
  value={stats.licenses.active}
  icon={CheckCircle2}
  tone="success"
  onClick={() => navigate("/licenses?is_expired=False...")}
/>
```

**Visual Details:**
- **Size:** 140x76px (compact mode) on desktop
- **Layout:** Icon (left) + Text (right)
- **Icon:** 18px, in 32x32 container, tone-colored
- **Label:** 10.5px uppercase, muted
- **Value:** 24px bold, responsive sizing for long numbers
- **Hover:** Slight lift (-1px translate), shadow increase, border+ring
- **Active:** Scale 0.99, no translate

**Colors by Tone:**
- `tone="success"` → Green (Active)
- `tone="danger"` → Red (Expired)
- `tone="primary"` → Blue (Allotments, BOE total)
- `tone="warning"` → Amber (Expiring 7-30d)

**Example Grid:**
```tsx
<div className="grid grid-cols-2 gap-3 md:grid-cols-4">
  <StatCard compact label="Active" value={234} icon={CheckCircle2} tone="success" ... />
  <StatCard compact label="Expired" value={12} icon={AlertTriangle} tone="danger" ... />
  <StatCard compact label="Allotments" value={156} icon={Network} tone="primary" ... />
  <StatCard compact label="BOE" value={89} icon={ReceiptText} tone="primary" ... />
</div>
```

---

### 2.3 EXPIRING SOON Table

**Purpose:** Show next 30 days of license expirations, sortable, actionable  
**Location:** Full width, below snapshot  
**Height:** Fixed at 400px (scrollable overflow)  
**Row count:** First 10 visible, "Load more" if > 10

#### Table Structure

**Columns:**
1. **License number** (40% width, left-aligned)
   - Clickable, navigates to /licenses?search={number}
   - Tone: primary (blue)
   - Font: Mono or medium weight

2. **Expiry date** (20% width, center-aligned)
   - Format: "01 Oct 2026"
   - Font: Regular text, muted

3. **Balance (CIF)** (20% width, right-aligned)
   - Format: "$45,234.50" (currency)
   - Font: Mono (tabular-nums)
   - Muted if < $5K (low balance indicator?)

4. **Days remaining** (12% width, right-aligned)
   - Calculation: `Math.ceil((expiry_date - today) / 86400000)`
   - Format: "6 days", "1 day", "0 days", "Expired"

5. **Status badge** (8% width, center-aligned)
   - **Calculated from days:**
     - ≤ 0: Red "Expired", `variant="destructive"`
     - 1-7: Red "N days", `variant="destructive"` (tone="danger")
     - 8-15: Amber "N days", `variant="default"` (tone="warning")
     - 16-30: Slate "N days", `variant="secondary"` (tone="neutral")

#### Row Styling

**Default state:**
- Border-bottom: 1px solid border/60
- Padding: 12px 16px
- Text: 14px
- Line-height: 1.5

**Hover state:**
- Background: accent/40
- Cursor: pointer
- Border-bottom: same (no change)

**Focus state (keyboard nav):**
- Background: accent/60
- Outline: 2px focus ring

**Accessible navigation:**
- Tab through rows
- Enter/Space to navigate to license detail

#### Empty State

If no licenses expiring in next 30 days:
```tsx
<EmptyState
  icon={CheckCircle2}
  title="All clear"
  description="No licenses are expiring in the next 30 days."
  size="default"
/>
```

**Example Table Code:**
```tsx
<Card className="overflow-hidden">
  <CardHeader className="border-b">
    <h3 className="text-sm font-semibold">Expiring soon</h3>
    <p className="text-xs text-muted-foreground">Next 30 days</p>
  </CardHeader>
  <CardContent className="max-h-[400px] overflow-auto p-0">
    <table className="w-full text-sm">
      <thead className="sticky top-0 bg-muted/80 backdrop-blur">
        <tr className="border-b">
          <th className="px-4 py-2.5 text-left">License</th>
          <th className="px-4 py-2.5 text-center">Expiry</th>
          <th className="px-4 py-2.5 text-right">Balance</th>
          <th className="px-4 py-2.5 text-right">Days</th>
          <th className="px-4 py-2.5">Status</th>
        </tr>
      </thead>
      <tbody>
        {expiringLicenses.map(lic => (
          <tr key={lic.id} className="border-t hover:bg-accent/40">
            <td className="px-4 py-2.5 text-primary font-medium">{lic.license_number}</td>
            <td className="px-4 py-2.5 text-center text-muted-foreground">{displayDate(lic.expiry_date)}</td>
            <td className="px-4 py-2.5 text-right tabular-nums">{displayMoney(lic.balance_cif)}</td>
            <td className="px-4 py-2.5 text-right">{days} days</td>
            <td className="px-4 py-2.5"><Badge variant={...}>{status}</Badge></td>
          </tr>
        ))}
      </tbody>
    </table>
  </CardContent>
</Card>
```

---

### 2.4 RECENT ACTIVITY Grid (BOE + Allotments)

**Purpose:** Show recent operational work with minimal scrolling  
**Location:** Full width, below expiring table  
**Layout:** 2-column (desktop), 1-column (tablet/mobile)  
**Height:** 300px each (scrollable)

#### Left Column: Recent BOE Entries

**Columns:**
1. **Date** (20% width, left-aligned)
   - Format: "24 Sep 2026"
   - Muted text

2. **BOE number** (25% width, left-aligned)
   - Clickable, navigates to /bill-of-entries/{id}/edit
   - Tone: primary

3. **Importer/Company name** (45% width, left-aligned)
   - Truncated with ellipsis
   - Max-width: 240px
   - Title attribute for full name

4. **Status indicator** (10% width, right-aligned)
   - If has pending invoice: 🟡 badge "Pending"
   - If invoiced: 🟢 badge "Invoiced"
   - If no invoice data: ⚪ neutral

#### Right Column: Recent Allotments

**Columns:**
1. **Date** (20% width)
   - Modified date or creation date
   - Format: "24 Sep 2026"

2. **Item name** (35% width)
   - Truncated, title attribute
   - Medium weight

3. **Quantity** (22% width, right-aligned)
   - Tabular-nums
   - Format: "500.00"

4. **CIF FC Value** (23% width, right-aligned)
   - Tabular-nums
   - Format: "$5,234.50"

**Example Code:**
```tsx
<div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
  {/* Recent BOE */}
  <Card className="overflow-hidden">
    <CardHeader className="border-b">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-semibold">Recent BOE entries</h3>
        <Button variant="outline" size="sm" onClick={...}>View all</Button>
      </div>
    </CardHeader>
    <CardContent className="max-h-[300px] overflow-auto p-0">
      <table className="w-full text-sm">
        {/* ... */}
      </table>
    </CardContent>
  </Card>

  {/* Recent Allotments */}
  <Card className="overflow-hidden">
    <CardHeader className="border-b">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-semibold">Recent allotments</h3>
        <Button variant="outline" size="sm" onClick={...}>View all</Button>
      </div>
    </CardHeader>
    <CardContent className="max-h-[300px] overflow-auto p-0">
      <table className="w-full text-sm">
        {/* ... */}
      </table>
    </CardContent>
  </Card>
</div>
```

---

## 3. Color & Tone Reference

### Alert Card Tones

| Condition | Tone | Background | Border | Icon | Text |
|-----------|------|------------|--------|------|------|
| Expiring < 7 days | danger | danger/5 | danger/30 | AlertTriangle | Red |
| Missing DGFT | danger | danger/5 | danger/30 | FileX | Red |
| Pending invoices | warning | warning/5 | warning/30 | FileSpreadsheet | Amber |

### StatCard Tones

| Metric | Tone | Meaning |
|--------|------|---------|
| Active | success | Healthy |
| Expired | danger | Action needed |
| Allotments | primary | Neutral info |
| BOE | primary | Neutral info |

### Status Badge Tones (Tables)

| Status | Variant | Tone | CSS |
|--------|---------|------|-----|
| < 7 days | destructive | danger | Red |
| 7-15 days | secondary | warning | Amber |
| 16-30 days | secondary | neutral | Gray |
| Expired | destructive | danger | Red |

---

## 4. Typography Scale

| Element | Font-size | Font-weight | Line-height | Color |
|---------|-----------|-------------|-------------|-------|
| Page title | 24px / 1.625rem (sm) → 30px (lg) | 700 bold | 1.2 | foreground |
| Section title | 16px | 600 semibold | 1.2 | foreground |
| Card header | 14px | 600 semibold | 1.2 | foreground |
| Table header | 12px | 600 semibold | 1.2 | muted-foreground |
| Table cell | 14px | 400 normal | 1.5 | foreground |
| Stat label | 10.5px | 600 semibold | 1 | muted-foreground |
| Stat value | 24px (default) → 18px (long) | 700 bold | 1 | foreground |
| Muted text | 13px | 400 normal | 1.5 | muted-foreground |
| Small text | 12px | 400 normal | 1.5 | muted-foreground |

---

## 5. Spacing Reference

| Element | Padding/Margin | Example |
|---------|-----------------|---------|
| Page header | px-5 py-4 (sm: px-6 py-5) | Top section |
| Card header | px-5 pt-5 pb-4 | Inside cards |
| Card content | px-5 pb-5 | Inside cards |
| Table cell | px-4 py-2.5 | Row height 44px |
| Gap between sections | mb-6 | Below each major section |
| Gap between cards | gap-3 / gap-4 | In grids |

---

## 6. Responsive Breakpoints

| Breakpoint | Width | Grid Layout |
|------------|-------|-------------|
| Mobile | < 640px | 1 col (alerts, snapshot) |
| Tablet | 640px–1024px | 2 col (alerts, snapshot, activity) |
| Desktop | 1024px+ | 3-4 col (alerts), 4 col (snapshot), full-width (tables) |
| XL | 1280px+ | Same as desktop (more breathing room) |

---

## 7. Animation & Interaction

### Hover Effects
- **StatCard:** Lift (-1px), shadow increase, border opacity +20%
- **Table rows:** Background accent/40, cursor pointer
- **Buttons:** Standard button animation (shadow, scale)
- **Alert cards:** Subtle lift, border opacity +20%

### Transitions
- All hovers: `transition-all duration-200`
- No delays (immediate feedback)

### Loading States
- Skeleton: Pulsing gray placeholders
- Refresh spinner: `animate-spin` on RefreshCw icon
- Table: Show skeleton rows if initial load

### Focus States
- Keyboard focus: 2px ring with 40% opacity (ring-ring/40)
- Tab order: Header buttons → Alert cards → StatCard → Table rows
- Visible on all interactive elements

---

## 8. Dark Mode Considerations

### CSS Variable Strategy
All colors use `var(--tb-*)` CSS variables:
- `var(--tb-brand)` → Primary blue
- `var(--tb-success)` → Green
- `var(--tb-warning)` → Amber
- `var(--tb-danger)` → Red
- `var(--tb-text)` → Foreground
- `var(--tb-text-secondary)` → Muted text
- `var(--tb-card-bg)` → Card background
- `var(--tb-border)` → Border color

### No hardcoded colors in component
Example (❌ DON'T):
```tsx
className="bg-white text-gray-800"  // ❌ Light-only
```

Example (✅ DO):
```tsx
className="bg-card text-foreground"  // ✅ Uses CSS vars
```

---

## 9. Accessibility Checklist

- [ ] All interactive elements keyboard-accessible (Tab, Enter, Space)
- [ ] Color not sole indicator of status (use text + icon)
- [ ] Text contrast ≥ 4.5:1 for all text
- [ ] Form fields have associated labels
- [ ] Images/icons have aria-label or title
- [ ] Tables have ARIA markup (`role="table"`, `scope="col"`)
- [ ] Live regions for status updates (`aria-live="polite"`)
- [ ] Semantic HTML (buttons, not divs)
- [ ] Focus indicators visible (ring-ring)
- [ ] No keyboard traps

---

## 10. Implementation Checklist (Phase 2)

### Components to Create
- [ ] `AlertCard.tsx` — Alert card with icon/count/action
- [ ] Update `Dashboard.tsx` layout structure
- [ ] Decompose into section components (optional, may skip for Phase 2)

### Components to Modify
- [ ] `Dashboard.tsx` — Main refactor
- [ ] Verify StatCard compact mode works as specified
- [ ] Verify Button variants and sizes

### Design System Verification
- [ ] Lint: `npm run lint` ✅
- [ ] Type check: `npm run typecheck` ✅
- [ ] Build: `npm run build` ✅
- [ ] Visual test (dev server): Responsive on mobile/tablet/desktop ✅
- [ ] Dark mode test: Switch theme, verify contrast ✅
- [ ] Keyboard nav test: Tab through all elements ✅

### Testing
- [ ] Update `Dashboard.test.tsx` snapshots
- [ ] Test data-rich state (many alerts, many expirations)
- [ ] Test empty state (no alerts, no data)
- [ ] Test loading state (skeleton cards)
- [ ] Test error state (failed API call)

---

**End of Visual Specification — Ready for Phase 2 Implementation**
