# Data Presentation & Formatting

**Last Updated:** 2026-09-25  
**Owner:** Product Designer + Frontend Engineer  
**Scope:** All numeric, currency, date, status, and progress displays

## Overview

Professional data presentation requires consistent formatting rules that make information scannable, comparable, and actionable. This spec covers numbers, currencies, dates, status indicators, and other data types.

---

## Numbers

### Whole Numbers

**Format Rule:** Use thousand separators for clarity

**Examples:**
- 1,000 (one thousand)
- 10,50,000 (Indian numbering: ten million fifty thousand) — use when appropriate for region
- 1234 → 1,234 (in most contexts)

**Alignment:** Right-aligned in tables (see Table System spec)

**Font:** Monospace or tabular numerals for tables
```css
.tabular-nums {
    font-variant-numeric: tabular-nums;
}
```

### Decimal/Floating-Point Numbers

**Precision Rule:** 2–4 decimal places depending on context

| Context | Precision | Example |
|---------|-----------|---------|
| Currency (INR/USD) | 2 decimals | 1,26,90,443.00 |
| Weight (kg, MT) | 2–3 decimals | 250.50 MT, 1500.250 kg |
| Percentage | 2 decimals | 45.32%, 0.50% |
| Exchange rate | 2–4 decimals | 1 USD = 83.25 INR |
| Scientific/Tech | 4+ decimals | Per domain spec |

**Display Rule:** Never show trailing zeros unless semantically important

- Bad: 100.00 (when 100 is the natural value)
- Good: 100 or 100.00 (for currency, always 2 decimals)

**Alignment:** Right-aligned with decimal point alignment (tabular numerals)

### Negative Numbers

**Format:** Use minus sign or parentheses
- Standard: `-1,234.56`
- Accounting: `(1,234.56)` — only for financial statements
- Never use red text alone (violates color-only rule)

**Color:** Use `--tb-danger` text with icon (e.g., ⬇️ TriangleDown)

```tsx
<span className="text-danger flex items-center gap-1">
  <TrendingDown size={14} />
  -1,234.56
</span>
```

### Large Numbers (Abbreviation)

For dashboard displays, abbreviate large numbers with secondary full value:

**Format Rules:**
- 1,000–999,999 → Show as is (e.g., 50,000)
- 1,000,000–999,999,999 → Use Lakh/Crore (India) or M/B (global)
- 1 Lakh = 100,000 (1,00,000)
- 1 Crore = 10,000,000 (1,00,00,000)

**Display:**
```tsx
<StatCard
  label="Total Value"
  value="1,45,67,890"  // Displayed value
  secondaryValue="1 Cr 45 L"  // Abbreviated
  title="1,45,67,890.00"  // Hover tooltip with full precision
/>
```

**Abbreviation Mapping:**
```javascript
const abbreviate = (num) => {
    if (num >= 10000000) return `${(num / 10000000).toFixed(2)} Cr`;  // Crore
    if (num >= 100000) return `${(num / 100000).toFixed(2)} L`;  // Lakh
    if (num >= 1000) return num.toLocaleString();
    return num;
};
```

---

## Currency

### INR (Indian Rupee)

**Format:** Indian numbering with comma separators

| Value | Format |
|-------|--------|
| 1,000 | 1,000 |
| 10,000 | 10,000 |
| 100,000 | 1,00,000 |
| 1,000,000 | 10,00,000 |
| 10,000,000 | 1,00,00,000 |

**Symbol Placement:** Rupee symbol before or after (preference: after)
- `₹ 1,26,90,443.00` or `1,26,90,443.00 ₹`

**Decimal Places:** Always 2 decimals for finality

**Alignment:** Right-aligned with tabular numerals

**Example in HTML:**
```tsx
<span className="tabular-nums text-right">
  ₹ 1,26,90,443.00
</span>
```

### USD (US Dollar)

**Format:** Standard US comma separators

| Value | Format |
|-------|--------|
| 1,000 | $1,000.00 |
| 10,000 | $10,000.00 |
| 1,000,000 | $1,000,000.00 |

**Symbol Placement:** Before the amount
- `$ 5,00,000.00` or `$5,00,000.00`

**Decimal Places:** Always 2 decimals

**Alignment:** Right-aligned with tabular numerals

### Multi-Currency Display

When showing both INR and USD side-by-side (e.g., BOE line items):

```tsx
<div className="flex justify-between gap-4">
  <div>
    <span className="text-muted-foreground text-xs">INR</span>
    <div className="tabular-nums font-semibold">
      ₹ 1,26,90,443.00
    </div>
  </div>
  <div>
    <span className="text-muted-foreground text-xs">USD</span>
    <div className="tabular-nums font-semibold">
      $ 1,52,500.00
    </div>
  </div>
</div>
```

### Utility Function

**File:** `frontend/src/utils/currencyFormatter.js`

```javascript
export const formatCurrency = (amount, currency = "INR", decimals = 2) => {
    if (amount === null || amount === undefined) return "—";
    
    const num = parseFloat(amount);
    if (isNaN(num)) return "—";
    
    const formatted = new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(num);
    
    return formatted;
};

// Usage:
// formatCurrency(1269044300, "INR") → "₹ 1,26,90,44,300.00"
// formatCurrency(5000.5, "USD") → "$ 5,000.50"
```

---

## Percentages

### Basic Percentages

**Format:** Number with 2 decimals + % symbol

| Value | Display |
|-------|---------|
| 0.5 | 0.50% |
| 45.3 | 45.30% |
| 100 | 100.00% |
| -5.25 | -5.25% |

**Alignment:** Right-aligned in tables

**Color:**
- Positive (↑): `--tb-success` text
- Negative (↓): `--tb-danger` text
- Neutral (0): `--tb-text`

**Example:**
```tsx
<span className={value >= 0 ? "text-success" : "text-danger"}>
  {value.toFixed(2)}%
</span>
```

### Percentage with Delta

Show change from previous period:

```tsx
<div className="flex items-center gap-2">
  <span className="text-sm">Current: 45.32%</span>
  <span className={`flex items-center gap-1 ${prev < curr ? "text-success" : "text-danger"}`}>
    {prev < curr ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
    {(curr - prev).toFixed(2)}%
  </span>
</div>
```

### Progress Bars

For percentage-based progress (completion, allocation):

```tsx
<div className="flex items-center gap-3">
  <div className="flex-1">
    <div className="h-2 bg-muted rounded-full overflow-hidden">
      <div 
        className="h-full bg-success transition-all"
        style={{ width: `${percentage}%` }}
      />
    </div>
  </div>
  <span className="text-xs font-semibold text-muted-foreground">
    {percentage.toFixed(0)}%
  </span>
</div>
```

---

## Dates & Times

### Date Format (ISO Standard)

**Format:** YYYY-MM-DD (unambiguous, sortable)

**Examples:**
- 2026-09-25 (25 September 2026)
- 2025-01-15 (15 January 2025)
- 2024-12-31 (31 December 2024)

**Font:** Monospace for clarity (especially in tables)
```css
.table td.date {
    font-family: var(--tb-font-mono);
}
```

**Alignment:** Left-aligned (or center in dense tables)

### Date Format (Display)

For user-facing surfaces (not sorting, more readable):

**Format:** Month Day, Year or localized format

**Examples:**
- September 25, 2026
- 25 Sep 2026 (abbreviated)
- 25-09-2026 (European)

**Localization:** Adjust format per region/user preference

### Date Ranges

**Format:** `start_date – end_date`

**Examples:**
```
2026-01-01 – 2026-03-31  (ISO, tabular)
Jan 1 – Mar 31, 2026     (Display, user-facing)
```

**Implementation:**
```tsx
const formatDateRange = (start, end) => {
    const s = new Date(start).toLocaleDateString('en-IN', {
        year: 'numeric', month: 'short', day: 'numeric'
    });
    const e = new Date(end).toLocaleDateString('en-IN', {
        year: 'numeric', month: 'short', day: 'numeric'
    });
    return `${s} – ${e}`;
};
```

### Timestamps

When showing time-of-day (audit logs, activity):

**Format:** HH:MM:SS (24-hour)

**Example:** `2026-09-25 14:30:45` (full timestamp with ISO date)

**Font:** Monospace

**Example:**
```tsx
<div className="font-mono text-xs text-muted-foreground">
  2026-09-25 14:30:45
</div>
```

### Relative Dates

For recent activity (less than 1 week old):

**Format:** "2 hours ago", "3 days ago"

**Fallback:** Show absolute date if older than 1 week

```javascript
export const formatRelativeDate = (date) => {
    const now = new Date();
    const past = new Date(date);
    const diffMs = now - past;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return past.toISOString().split('T')[0];  // Fallback to YYYY-MM-DD
};
```

### Utility Function

**File:** `frontend/src/utils/dateFormatter.js` (already exists)

```javascript
export const formatDate = (date) => {
    if (!date) return null;
    const d = new Date(date);
    return d.toISOString().split('T')[0];  // YYYY-MM-DD
};

export const formatDateDisplay = (date) => {
    if (!date) return null;
    return new Date(date).toLocaleDateString('en-IN', {
        year: 'numeric', month: 'short', day: 'numeric'
    });
};
```

---

## Status & Badges

### Status Indicators

Use semantic tones with icon + text (never color alone):

**Allowed Tones:** primary, success, warning, danger, info, neutral

**Mapping:**
| Status | Tone | Icon | Color |
|--------|------|------|-------|
| Active / Approved | success | ✓ | Green |
| Pending / Draft | warning | ⏱️ | Amber |
| Inactive / Rejected | danger | ✗ | Red |
| Processing | info | ⟳ | Blue |
| Default / Neutral | neutral | — | Gray |

**HTML:**
```tsx
// Status badge with semantic color
<span className="inline-flex items-center gap-1 rounded-md px-2 py-1 bg-success/10 text-success text-xs font-medium border border-success/20">
  <Check size={14} />
  Approved
</span>
```

**Implementation:**
```tsx
import { TONE_MAP } from "@/theme/tokens";
import { tone as resolveTone } from "@/theme/tokens";

const StatusBadge = ({ status, icon: Icon }) => {
    const t = resolveTone(TONE_MAP, status);
    return (
        <span
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium"
            style={{
                backgroundColor: `${t.bg}`,
                color: `${t.fg}`,
                border: `1px solid ${t.border}`,
            }}
        >
            {Icon && <Icon size={14} />}
            {status}
        </span>
    );
};
```

### Condition Badges (DFIA License)

Use `CONDITION_BADGE_PALETTE` from `theme/tokens.js`:

```tsx
import { CONDITION_BADGE_PALETTE } from "@/theme/tokens";

const badge = CONDITION_BADGE_PALETTE["AU"];
// { bg: "#DBEAFE", color: "#1E3A8A", label: "AU" }
```

**Palette:**
- AU (Authorization) → Blue
- 2% (Duty) → Red
- 3% (Duty) → Orange
- 5% (Duty) → Amber
- 10% (Duty) → Green

### Multi-Status Display

When showing multiple status badges (e.g., license with multiple conditions):

```tsx
<div className="flex flex-wrap gap-2">
  {conditions.map(c => (
    <span key={c} style={CONDITION_BADGE_PALETTE[c]}>
      {c}
    </span>
  ))}
</div>
```

---

## Progress & Metrics

### Progress Bar (Linear)

For allocation, usage, or completion percentage:

```tsx
<div className="w-full">
  <div className="h-2 bg-muted rounded-full overflow-hidden">
    <div
      className="h-full bg-success transition-all duration-300"
      style={{ width: `${(allocated / total) * 100}%` }}
    />
  </div>
  <div className="mt-2 flex justify-between text-xs text-muted-foreground">
    <span>{allocated.toLocaleString()} / {total.toLocaleString()}</span>
    <span>{((allocated / total) * 100).toFixed(1)}%</span>
  </div>
</div>
```

**Color Mapping:**
- Success: 0–70% used
- Warning: 70–90% used
- Danger: 90%+ used

### Mini Gauge / Circular Progress

For compact status displays (e.g., dashboard):

```tsx
<div className="flex items-center gap-3">
  <svg className="w-12 h-12">
    <circle cx="24" cy="24" r="20" fill="none" stroke="var(--tb-border)" strokeWidth="2" />
    <circle
      cx="24" cy="24" r="20"
      fill="none"
      stroke="var(--tb-success)"
      strokeWidth="2"
      strokeDasharray={`${percentage * 1.26} 126`}
      strokeLinecap="round"
      transform="rotate(-90 24 24)"
    />
  </svg>
  <div>
    <div className="text-2xl font-bold">{percentage.toFixed(0)}%</div>
    <div className="text-xs text-muted-foreground">Complete</div>
  </div>
</div>
```

### Balance Summary

Common in License Manager (allocated, available, debited):

```tsx
<div className="grid grid-cols-3 gap-4">
  <StatCard
    label="Total Allocated"
    value="1,00,000 MT"
    icon={Layers}
    tone="primary"
  />
  <StatCard
    label="Debited"
    value="75,000 MT"
    icon={Download}
    tone="success"
  />
  <StatCard
    label="Available"
    value="25,000 MT"
    icon={Box}
    tone="info"
  />
</div>
```

---

## Null / Missing Data

**Display:** Dash (em-dash or en-dash)

**Format:** `—` (em-dash, preferred) or `-` (if em-dash unavailable)

**Color:** `--tb-text-muted`

**Usage:**
```tsx
const formatValue = (value) => {
    if (value === null || value === undefined || value === "") {
        return <span className="text-muted-foreground">—</span>;
    }
    return value;
};
```

**Never use:**
- "N/A" (verbose)
- "null" (technical)
- Empty string (confusing)
- "0" (unless zero is legitimate)

---

## Large Data Sets

### Truncation Rules

For long text/numbers that might overflow:

```tsx
<div
  className="truncate"
  title={fullValue}  // Show full value on hover
>
  {truncatedValue}
</div>
```

**Examples:**
- License number: full display (always visible)
- Exporter name: truncate after 40 chars → tooltip on hover
- Description: truncate after 60 chars → "Show more" link
- Currency: right-align, don't wrap

### Line Clamping

For multi-line text that should limit:

```tsx
<div className="line-clamp-2">  {/* Show max 2 lines */}
  {description}
</div>
```

---

## Dark Mode

All data formatting respects dark mode via CSS variables:

- Text color: `--tb-text` (auto-switches)
- Muted text: `--tb-text-muted`
- Status colors: Use `TONE_MAP` (respects dark mode)
- No hardcoded colors

**Test** with `[data-theme="dark"]` on root element.

---

## Accessibility

### Number Formatting

- Use monospace font for numeric columns (improves scannability)
- Use `tabular-nums` CSS property for alignment
- Sufficient contrast: AA minimum (4.5:1 for small text)

### Status Indicators

- Never rely on color alone
- Include icon + text (e.g., ✓ Approved)
- Use `aria-label` for semantic meaning

```tsx
<span
  aria-label="License status: approved"
  className="inline-flex items-center gap-1 text-success"
>
  <Check size={14} />
  Approved
</span>
```

### Date/Time

- Use ISO format (YYYY-MM-DD) for programmatic sorting
- Provide alt text: `title="September 25, 2026"`
- Consider locale when displaying to users

### Currency

- Use proper currency code (INR, USD) in labels
- Include symbol + text (e.g., ₹ 100.00)
- Don't rely on symbol alone for screen readers

---

## Validation Checklist

Before shipping data displays:

- [ ] Numbers use thousand separators (1,000 not 1000)
- [ ] Currency always shows 2 decimals (1,000.00)
- [ ] Dates use ISO format YYYY-MM-DD (in tables/data)
- [ ] Percentages show 2 decimals (45.30%)
- [ ] Status badges include icon + text (never color alone)
- [ ] Null values show em-dash "—"
- [ ] Numeric columns are right-aligned
- [ ] Text truncation includes hover tooltip
- [ ] Colors use `TONE_MAP` tokens (never hardcoded)
- [ ] Monospace font used for numeric/date columns
- [ ] `tabular-nums` CSS applied to numeric columns
- [ ] Accessibility: `aria-label` on status badges
- [ ] Dark mode tested with `[data-theme="dark"]`
- [ ] Screen reader tested for semantic meaning

---

## Common Patterns

### License Balance Card

```tsx
<div className="grid grid-cols-3 gap-4">
  <StatCard
    label="Initial Balance"
    value="1,00,000.00 MT"
    secondaryValue="1 Lakh MT"
    tone="info"
  />
  <StatCard
    label="Total Debited"
    value="75,000.50 MT"
    secondaryValue="75 L MT"
    tone="success"
  />
  <StatCard
    label="Remaining"
    value="24,999.50 MT"
    secondaryValue="25 L MT"
    tone="primary"
  />
</div>
```

### License Item Row (Table)

```
| License # | Exporter | Qty (MT) | Value (₹) | Status |
|-----------|----------|----------|-----------|--------|
| IMP-001 | Acme Corp | 500.00 | ₹1,00,00,000.00 | ✓ Approved |
| IMP-002 | XYZ Inc | 250.50 | ₹ 50,00,000.00 | ⏱️ Pending |
```

### BOE Line Item (Detail)

```
Item Name: Premium Vegetable Oil
Quantity: 250.50 MT
CIF (INR): ₹ 50,00,000.00
CIF (USD): $ 60,000.00
Purchase Status: GE (Global Exim)
Condition: AU (Authorization)
```

---

## Files & Resources

- `frontend/src/utils/dateFormatter.js` — Date formatting
- `frontend/src/utils/currencyFormatter.js` — Currency formatting (reference)
- `frontend/src/theme/tokens.js` — Semantic colors and tone maps
- `frontend/src/theme/tabler.css` — Token definitions (--tb-* variables)
