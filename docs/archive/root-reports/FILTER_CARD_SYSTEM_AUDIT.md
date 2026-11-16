# Filter & Card System Audit Report

**Hotfix Branch:** hotfix/ui-consistency-2026-09-25  
**Date:** 2026-09-25  
**Status:** AUDIT COMPLETE

---

## EXECUTIVE SUMMARY

The application has **good foundational components** for filters and cards, but **inconsistent implementations across pages** create visual drift and UX friction. 

- **FilterPanel component** exists but is minimal (basic structure only)
- **Card component** is well-designed (shadcn/ui pattern, flexible)
- **Filter implementations** vary significantly in spacing, field heights, and layout patterns
- **Custom cards** (StatCard, EntityCard) are task-specific; general-purpose Card usage is growing

**Recommendation:** Standardize on FilterPanel usage across all filter-heavy pages; promote Card/CardContent/CardHeader patterns in new work; document measurements.

---

## PHASE 1: FILTER SYSTEM AUDIT

### 1.1 FilterPanel Component (Current)

**Location:** `frontend/src/components/filters/FilterPanel.tsx`

**Measurements:**
| Metric | Value |
|--------|-------|
| Container padding | `p-3` (12px all sides) |
| Header height | `min-h-11` (44px) |
| Header padding | `px-3 py-2` (12px H, 8px V) |
| Row gap (FilterGrid) | `gap-3` (12px) |
| Border | `1px border-border/70` |
| Border radius | `rounded-lg` (0.5rem = 8px) |
| Background | `bg-card` |
| Shadow | `shadow-sm` |
| Grid columns | 1 (mobile), 2 (sm), 4 (xl) |

**Features:**
- Basic structure: title + icon + active count + clear button
- Responsive grid (FilterGrid wrapper)
- Field wrapper (FilterField) with `wide` prop for xl:col-span-2
- Loading state indicator

**Usage:** AllotmentFilters, AdvancedFilter (via import)

**Issues Identified:**
1. No label styling provided (callers add their own `form-label`)
2. No standard field height (callers use h-8, h-9, h-10 variably)
3. No built-in support for date range, select, multi-select field types
4. Clear button position/style not customizable

---

### 1.2 AllotmentFilters

**Location:** `frontend/src/pages/AllotmentFilters.tsx`

**Structure:**
- Uses FilterPanel + FilterGrid
- 16 filter fields across 2+ rows
- Mix of: text inputs, selects, react-select, DateRangeFilter

**Measurements:**
| Metric | Value |
|--------|-------|
| Input field height | `h-8` (32px) |
| Input padding | `px-2 py-1` (8px H, 4px V) |
| Input border radius | `rounded-md` (0.375rem = 6px) |
| Input font size | `text-[13px]` |
| Label font size | `text-[11px]` |
| Label class | `form-label` (custom CSS) |
| Row spacing | Implicit from FilterGrid `gap-3` |
| Date range component | Spans 2 columns (sm:col-span-2) |

**Field Types:**
- Text inputs (license number, description, HS code)
- Native selects (license status, debit based on)
- react-select multi-select (purchase status)
- HybridSelect async (exporter, norm class)
- DateRangeFilter (expiry date range)

**Layout:** FilterGrid auto-wraps; DateRangeFilter manually spans 2 cols

---

### 1.3 ItemPivotFilters

**Location:** `frontend/src/pages/reports/ItemPivotFilters.tsx`

**Structure:**
- Custom filter panel (not using FilterPanel component)
- Own header with icon, title, clear button
- 6 main filter rows with labeled grid

**Measurements:**
| Metric | Value |
|--------|-------|
| Container padding | `px-3 py-3 sm:px-4 sm:py-4` (12–16px) |
| Header padding | `px-3 py-3 sm:px-4` |
| Grid columns | 1 (mobile), 2 (sm), 4 (lg) |
| Grid gap | `gap-2 sm:gap-3 lg:gap-4` (8–16px) |
| Field height | `h-9` (36px) |
| Input border radius | `rounded-md` (6px) |
| Border | `border-border` |
| Label font weight | `font-bold` |
| Label spacing | `mb-2` (8px) |
| Active filters banner | Full-width alert below grid |
| Active filter chips | `chip chip-primary text-xs` |

**Field Types:**
- Native selects (min balance, license status)
- react-select multi (purchase status)
- DateRangeFilter (expiry date)
- AsyncSelectField (include/exclude companies)

**Layout:** Grid with active filters displayed below in alert box

**Spacing Precision:**
- Fields are more spacious than AllotmentFilters (h-9 vs h-8)
- Icons + labels consistently present
- Multi-select fields have explicit `minHeight: '38px'` container

---

### 1.4 ItemReportFilters

**Location:** `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`

**Structure:**
- Custom filter panel (not using FilterPanel component)
- Modeled after ItemPivotFilters
- 3 rows of grid (main filters, secondary, text search)
- Full-width alert for active filters

**Measurements:**
| Metric | Value |
|--------|-------|
| Container div class | `surface-card` (likely `bg-card`) |
| Header padding | `px-4 py-3.5` |
| Grid gap | `gap-3` |
| Grid columns | 1 (default), 2 (sm), 3 (lg) |
| Field height | `h-9` (36px) |
| Input border radius | `rounded-md` (6px) |
| Label class | `form-label font-bold mb-2` |
| Wide fields | `sm:col-span-2` or `sm:col-span-full` for text search |
| Active filters | Full-width alert box below |

**Field Types:**
- Native selects (min balance, min qty, license status, restricted)
- react-select multi (purchase status, norms, notifications, item names)
- DateRangeFilter (expiry date)
- AsyncSelectField (companies include/exclude)
- Text inputs (product description, HSN code)

---

### 1.5 License Ledger Filters

**Location:** `frontend/src/pages/LicenseLedger.tsx` (inline) + `frontend/src/pages/licenseLedgerFilters.ts` (config)

**Filter Configuration:**
```typescript
interface LicenseLedgerFilters {
  company: SelectValue;
  licenseType: string;
  minBalance: string;
  search: string;
  ordering: string;
  activeOnly: boolean;
  norm: SelectValue;
  purchaseStatus: SelectValue;
  purchaseBill: string;
  purchaseDateFrom: string;
  purchaseDateTo: string;
  licenseNumbers: string;
  excludeLicenseNumbers: string;
}
```

**In-page implementation:**
- Uses AsyncSelectField, DateRangeFilter, native selects
- Switch for `activeOnly` toggle
- No dedicated FilterPanel usage
- Scattered throughout page header area

---

### 1.6 AdvancedFilter Component

**Location:** `frontend/src/components/AdvancedFilter.tsx`

**Usage:** Used by FilterPanel; wraps custom filter logic

**Notes:** Minimal wrapper; largely delegated to page implementations

---

### 1.7 DateRangeFilter Component

**Location:** `frontend/src/components/DateRangeFilter.tsx`

**Key Props:**
- `label` (required)
- `fromValue`, `toValue` (string dates)
- `onFromChange`, `onToChange`, `onClear` callbacks
- `icon` (optional LucideIcon)
- `fromId`, `toId` (optional, for labels)

**Usage:** AllotmentFilters, ItemPivotFilters, ItemReportFilters, LicenseLedger

---

## PHASE 2: DESIGN FINDINGS

### Filter Panel Architecture

**Current Gaps:**
1. **No standardized field type support** — callers build their own input/select/async combinations
2. **Inconsistent heights** — h-8 (AllotmentFilters) vs h-9 (ItemPivotFilters)
3. **Label styling varies** — some use `form-label text-[11px]`, others `form-label font-bold`
4. **Date range not integrated** — imported separately, not a first-class FilterField type
5. **Async selects hardcoded** — HybridSelect/AsyncSelectField not wrapped

### Measurement Standardization Needed

| Property | Current | Recommended |
|----------|---------|-------------|
| Field height | h-8, h-9 | h-9 (36px) |
| Input padding | Varies | `px-3 py-1` (12px H, 4px V) |
| Label bottom margin | Varies (mb-0, mb-1.5, mb-2) | `mb-2` (8px) |
| Field bottom margin | None (gap-based) | Keep gap-based (gap-3) |
| Border radius | `rounded-md` (6px) | Consistent `rounded-md` |
| Icon size (labels) | Varies | `size-4` (16px) |

---

## PHASE 3: CARD SYSTEM AUDIT

### 3.1 Card Component (shadcn/ui)

**Location:** `frontend/src/components/ui/card.tsx`

**Structure:**
```typescript
Card              // wrapper div
├─ CardHeader     // flex flex-col gap-1.5, px-5 pt-5
│  ├─ CardTitle   // font-semibold
│  └─ CardDescription // text-sm text-muted-foreground
├─ CardContent    // px-5 pb-5
└─ CardFooter     // flex items-center, px-5 pb-5
```

**Measurements:**
| Element | Padding | Border Radius | Shadow |
|---------|---------|---------------|--------|
| Card | — | `rounded-xl` (12px) | `shadow-sm` |
| CardHeader | `px-5 pt-5` | — | — |
| CardContent | `px-5 pb-5` | — | — |
| CardFooter | `px-5 pb-5` | — | — |
| Gap (header content) | `gap-1.5` | — | — |

**Background:** `bg-card` (CSS variable)  
**Border:** `1px border border-border`  
**Text Color:** `text-card-foreground`

**Features:**
- Responsive padding/gaps
- Semantic slot naming (`data-slot="card"`)
- Flexible layout (flexbox column)
- Border handling via selector `[.border-b]:pb-4`, `[.border-t]:pt-4` for dividers

**Usage:** 40+ files import; widely adopted

---

### 3.2 StatCard Component

**Location:** `frontend/src/components/StatCard.tsx`

**Purpose:** Display a metric with icon, label, value, optional secondary value

**Props:**
- `label: string` — uppercase label
- `value: React.ReactNode`
- `icon: LucideIcon`
- `tone?: "primary" | "success" | "danger" | "warning" | "info" | "neutral"`
- `onClick?: () => void` — makes it interactive
- `secondaryValue?: React.ReactNode` — small muted text under value
- `title?: string` — hover tooltip (full-precision value)
- `compact?: boolean` — denser padding/icon, length-aware value sizing

**Measurements (non-compact):**
| Metric | Value |
|--------|-------|
| Padding | `gap-4 px-5 py-4` |
| Icon size | `size-10` (40px) |
| Gap between icon & text | `gap-4` (16px) |
| Label font size | `text-[10.5px]` |
| Label font weight | `font-semibold` |
| Value font size | `text-[1.6rem]` (25.6px) |
| Value font weight | `font-bold` |
| Border radius | `rounded-lg` (8px) |
| Border | `border-border/60` |
| Shadow | `shadow-sm` |

**Measurements (compact mode):**
| Metric | Value |
|--------|-------|
| Padding | `gap-3 px-3.5 py-3` |
| Icon size | `size-9` (36px) |
| Value font size | Length-aware; defaults text-2xl, shrinks for long values |
| Value wrap | `whitespace-nowrap` |

**Tone Colors:**
Each tone defines: icon background, text color, hover ring, gradient glow

**Usage:** Dashboard, ReconciliationPanel, ReconciliationIssues, LicensePurchaseProfitReport, LicenseLedgerDetail

---

### 3.3 EntityCard Component

**Location:** `frontend/src/components/primitives/EntityCard.tsx`

**Purpose:** Reusable card layout for list items (Allotment, BOE, Trade records)

**Structure:**
```
EntityCard
├─ Header: title + chips + badges
├─ Body: children (optional)
├─ Summary row: stats + action buttons
├─ Detail section (expandable)
```

**Props:**
- `accent: string` — tone (primary, success, etc.)
- `title: React.ReactNode`
- `headerChips?: { icon?, label, tone? }[]`
- `statusBadges?: { tone, label, icon? }[]`
- `children?: React.ReactNode` — custom body content
- `summary?: { label, value, tone? }[]`
- `actions?: { icon, title, onClick, tone?, label? }[]`
- `detail?: () => React.ReactNode` — expandable detail section
- `onView?: () => void` — controlled detail toggle
- `viewOpen?: boolean` — controlled detail state

**Tone System:** Uses theme/tokens.js (`CHIP_TONE_MAP`, `ACTION_TONE_MAP`, `TEXT_TONE_MAP`)

**Usage:** AllotmentsTable, MasterList, TradesListView

---

### 3.4 Other Card Types

| Component | Location | Purpose |
|-----------|----------|---------|
| SionNormCard | `frontend/src/pages/license-overview/SionNormCard.tsx` | Display SION norms |
| StatCard (page-specific) | `frontend/src/pages/license-overview/StatCard.tsx` | Extended StatCard for dashboard |
| SummaryCard | `frontend/src/pages/license-overview/SummaryCard.tsx` | Summary metrics card |
| TradeConfigCard | `frontend/src/pages/TradeConfigCard.tsx` | Trade configuration display |
| MdsStatusCard | `frontend/src/pages/settings/MdsStatusCard.tsx` | Status indicator card |

---

## PHASE 4: CARD SYSTEM FINDINGS

### Cards Are Well-Structured

✓ **Card component (shadcn/ui):** Flexible, widely adopted (40+ pages)  
✓ **StatCard component:** Purpose-built for metrics, tone system, interactive  
✓ **EntityCard component:** Powerful for list items with actions & details  
✓ **Padding consistency:** px-5, pt-5, pb-5 (20px) standard

### Gaps & Inconsistencies

1. **No lightweight card variant** — all cards use full 20px padding; no "compact" option
2. **Entity card styling is CSS-based** — not using Card/CardHeader/CardContent (custom `.entity-card-*` classes)
3. **Page-specific StatCard** — diverges from main StatCard (license-overview/StatCard.tsx)
4. **No documented card patterns** — callers create custom cards instead of composing primitives

### Recommendation

- **Keep Card/CardHeader/CardContent pattern** for new general-purpose cards
- **StatCard** is the standard for metrics; use it instead of custom cards
- **EntityCard** is specialized; document when to use vs. Card
- Consider a **compact Card variant** for dense layouts (future)

---

## INTEGRATION ASSESSMENT

### Pages Using Filters

| Page | Current Filter Type | Component | Status |
|------|-------------------|-----------|--------|
| AllotmentFilters | FilterPanel + custom fields | Custom | ✓ Good |
| ItemPivotReport | Custom panel | Custom | ⚠ Inconsistent |
| ItemReport | Custom panel | Custom | ⚠ Inconsistent |
| LicenseLedger | Scattered (no panel) | Inline | ✗ Needs refactor |
| AdvancedFilter | Wrapper | FilterPanel | ✓ Good |

### Pages Using Cards

| Page | Card Type | Count | Status |
|------|-----------|-------|--------|
| Dashboard | StatCard | 5 | ✓ Good |
| ReconciliationPanel | Card + StatCard | Mix | ✓ Good |
| Reports (all) | Card + custom | Mix | ⚠ Inconsistent |
| License Overview | Card + StatCard | Mix | ⚠ Inconsistent |
| Admin pages | Card | 3+ | ✓ Good |

---

## PHASE 5: RECOMMENDATIONS & NEXT STEPS

### Short-term (This Hotfix)

**Filter System:**
1. Add `form-label mb-2 flex items-center gap-2` standard label styling to FilterPanel
2. Standardize field height to `h-9` (36px) across all filters
3. Document FilterPanel usage patterns in code comments
4. Consider: unified filter type definitions (see below)

**Card System:**
1. Standardize on Card/CardHeader/CardContent for new work
2. Phase out custom card styling in favor of shadcn/ui patterns
3. Document StatCard tone system in component comments
4. Document EntityCard usage (when not to use Card)

### Medium-term (Next Sprint)

**Filter Enhancement:**
```typescript
// Proposed: FilterField component with integrated label
interface FilterFieldProps {
  label: string;
  icon?: LucideIcon;
  type: 'text' | 'select' | 'date' | 'daterange' | 'multiselect' | 'async';
  value: any;
  onChange: (v: any) => void;
  options?: SelectOption[];
  endpoint?: string; // for async fields
  placeholder?: string;
  required?: boolean;
  wide?: boolean;
  children?: ReactNode; // for custom content
}
```

**Card Enhancement:**
- Add `variant="compact"` option to reduce padding for dense layouts
- Add `interactive` prop to Card for clickable cards
- Export a `CardAction` button component for consistency

### Documentation

**Create:** `docs/UI_COMPONENTS.md`
- Filter system architecture & measurement table
- Card system patterns & when to use each type
- StatCard tone system & examples
- EntityCard props & composition patterns
- Code examples for each pattern

---

## MEASUREMENT REFERENCE TABLE

### Input Fields

| Property | Standard | Notes |
|----------|----------|-------|
| Height | h-9 (36px) | Use consistently |
| Padding | px-3 py-1 | 12px H, 4px V |
| Border radius | rounded-md (6px) | Consistent across inputs |
| Border | border-input | CSS variable |
| Font size | text-sm (14px) | Standard form size |
| Label font | text-sm | For most labels |
| Label spacing | mb-2 (8px) | Below label, above field |
| Icon size | size-4 (16px) | In labels |

### Filter Panels

| Property | Standard | Notes |
|----------|----------|-------|
| Container padding | p-3 or px-3 py-3 | 12px or 12-16px |
| Row gap | gap-3 or gap-2 sm:gap-3 | 12px or 8-12px responsive |
| Header min-height | min-h-11 (44px) | Clickable targets |
| Border radius | rounded-lg or rounded-xl | 8px or 12px |
| Shadow | shadow-sm | Subtle depth |
| Grid columns | 1 / 2 / 3 / 4 | Responsive breakpoints |

### Cards

| Property | Standard | Notes |
|----------|----------|-------|
| Padding | px-5 py-4 or px-5 pt-5 | 20px horizontal, 16-20px vertical |
| Border radius | rounded-xl (12px) | More rounded than inputs |
| Shadow | shadow-sm | Consistent with panels |
| Gap (internal) | gap-1.5 (6px) | Between title & description |
| Border | border-border | CSS variable |

---

## FILES IMPACTED BY AUDIT

### Component Files
- `frontend/src/components/filters/FilterPanel.tsx`
- `frontend/src/components/ui/card.tsx`
- `frontend/src/components/StatCard.tsx`
- `frontend/src/components/primitives/EntityCard.tsx`
- `frontend/src/components/DataFilter.tsx`
- `frontend/src/components/DateRangeFilter.tsx`

### Page Files (Filters)
- `frontend/src/pages/AllotmentFilters.tsx`
- `frontend/src/pages/reports/ItemPivotFilters.tsx`
- `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`
- `frontend/src/pages/LicenseLedger.tsx`

### Page Files (Cards)
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/ReconciliationPanel.tsx`
- `frontend/src/pages/reports/ItemPivotReport.tsx`
- `frontend/src/pages/license-overview/LicenseOverviewPage.tsx`

---

## AUDIT SIGN-OFF

**Auditor:** Filter & Card System Specialist  
**Date:** 2026-09-25  
**Status:** ✓ COMPLETE

**Key Findings:**
1. Filters: Inconsistent field heights, label styling, and panel patterns
2. Cards: Good foundational components; some divergence in custom implementations
3. Measurements: Documented and ready for standardization
4. Recommendations: Provided for short and medium-term improvements

**Next Steps:** Update UI_AGENT_WORK_QUEUE.md with specific component fix tasks
