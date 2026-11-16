# Master UI/UX Audit — License Manager

**Date:** 2026-08-12  
**Scope:** Complete frontend review across spacing, typography, forms, tables, filters, search, dialogs, responsive behavior, accessibility, and component consolidation.

---

## Executive Summary

The License Manager frontend has a **strong foundational design system** built on shadcn/ui + Tailwind v4 + Radix UI, with good accessibility baseline and dark mode support. However, the audit reveals **20 areas requiring standardization and enhancement** to achieve WCAG AA compliance at scale, improve mobile UX, and reduce component duplication.

**Key Wins:**
- Centralized design tokens in `/src/styles/tailwind.css` (component layer)
- Semantic form validation with ARIA labels via `FormField` component
- Focus management in dialogs and confirmation flows
- Skeleton loading states with deterministic widths
- Dark mode support via `[data-theme="dark"]`

**Critical Gaps:**
- **Component duplication:** 2 card, 2 empty state, 3 button variants (ui/ vs primitives/)
- **Mobile responsiveness:** Tables overflow horizontally; no native mobile table views
- **Sync conflict display:** No dedicated UI for Master conflict resolution
- **Loading states:** Incomplete across async operations (search, exports, API calls)
- **Autocomplete UX:** `DebouncedAsyncSelect` lacks visual feedback, loading shimmer
- **Focus indicators:** Not visible on mobile (no `focus-visible` on all interactive elements)
- **Color contrast:** Some badge/text combinations need verification for WCAG AA

---

## Part 1: Spacing & Layout

### Current State

| Component | Spacing Pattern | Consistency |
|-----------|-----------------|-------------|
| Page Header | `gap-12`, `mb-20`, `pb-16` | ✅ Uniform |
| Card Body | `p-20` | ✅ Uniform |
| Card Header | `p-12` padding, `mb-20` bottom border | ⚠️ Inconsistent with body |
| Section Label | `mb-14` | ✅ Uniform |
| Alert | `p-12 p-16`, `mb-12` | ⚠️ Mixed padding |
| Tables | `p-8` (headers), `p-8` (cells) | ✅ Uniform |

### Findings

1. **Inconsistent card padding:** Card header uses `12px` but body uses `20px` — creates visual imbalance.
2. **Margin stacking:** Multiple components with `mb-*` can cause inconsistent spacing when stacked.
3. **Mobile gutters:** `container-fluid` relies on Bootstrap defaults; Tailwind responsive padding not explicitly defined.
4. **Form spacing:** Labels, inputs, errors all use different gap values (`mb-1.5`, `mt-0.5`, `gap-6`).

### Recommended Standardization

```css
/* In tailwind.css component layer */
@layer components {
  /* Consistent vertical rhythm: 4px base unit */
  .spacing-xs { gap: 4px; }      /* 4px */
  .spacing-sm { gap: 8px; }      /* 8px */
  .spacing-md { gap: 12px; }     /* 12px */
  .spacing-lg { gap: 16px; }     /* 16px */
  .spacing-xl { gap: 20px; }     /* 20px */
  .spacing-2xl { gap: 24px; }    /* 24px */
  
  /* Card standardization */
  .card-compact { padding: 12px 16px; }    /* Tables, dense lists */
  .card-standard { padding: 16px 20px; }   /* Forms, standard sections */
  .card-spacious { padding: 20px 24px; }   /* Hero sections, headers */
  
  /* Form field spacing */
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;  /* Label to input */
    margin-bottom: 16px;  /* Field to field */
  }
  .form-error {
    margin-top: 4px;
    font-size: 11.5px;
  }
}
```

### Responsive Spacing

Add mobile-specific spacing to ensure content breathes on smaller screens:

```html
<!-- Example: PageHeader with responsive padding -->
<div class="page-header px-4 sm:px-6 lg:px-8">
  <!-- content -->
</div>
```

**Action Items:**
- [ ] Audit all `.card-body`, `.card-header` for uniform padding
- [ ] Define explicit mobile padding via responsive utilities (e.g., `px-4 sm:px-6 lg:px-8`)
- [ ] Replace inline margin/gap with component classes
- [ ] Verify stacking behavior of `.page-header` + `.alert` + form groups

---

## Part 2: Typography & Hierarchy

### Current State

| Element | Size | Weight | Color | Usage |
|---------|------|--------|-------|-------|
| Page pretitle | 11px | 700 | secondary | Section labels |
| Page title | implicit | implicit | implied | **Missing from component** |
| Section header | 10.5px | 700 | secondary | Subsection markers |
| Dialog title | 15px | 600 | foreground | Modal headers |
| Table header | 11px | 700 | secondary | Table column labels |
| Badge | 11px | 600 | varies | Status indicators |
| Button text | 13px | 600 | foreground | CTA text |
| Form label | implicit | implicit | implicit | **No explicit class** |
| Error message | 11.5px | regular | destructive | Validation feedback |
| Helper text | not defined | — | — | **Missing entirely** |

### Findings

1. **No explicit `<h1>`–`<h6>` sizing:** Page titles use implicit browser defaults, not Tailwind.
2. **Form labels lack styling class:** Labels inherit from Label component; no `.form-label` utility.
3. **Missing helper text styling:** "Password must be 8+ chars" has no standard size/color.
4. **Inconsistent font weights:** Buttons are 600, headers are 700, inputs inherit system font-weight.
5. **No line-height standardization:** Rely on Tailwind defaults or inline styles.

### Recommended Typography Scale

```css
@layer components {
  /* Headings */
  .heading-h1 { @apply text-3xl font-bold leading-tight; }     /* 30px */
  .heading-h2 { @apply text-2xl font-bold leading-snug; }      /* 24px */
  .heading-h3 { @apply text-xl font-semibold leading-snug; }   /* 20px */
  .heading-h4 { @apply text-lg font-semibold leading-snug; }   /* 18px */
  .heading-h5 { @apply text-base font-semibold; }              /* 16px */
  .heading-h6 { @apply text-sm font-semibold; }                /* 14px */
  
  /* Body text */
  .body-lg { @apply text-base leading-relaxed; }               /* 16px, +1.5 line-height */
  .body-base { @apply text-sm leading-normal; }                /* 14px */
  .body-sm { @apply text-xs leading-normal; }                  /* 12px */
  
  /* Form labels */
  .form-label {
    @apply text-sm font-medium text-foreground;
  }
  
  /* Form helper text */
  .form-helper {
    @apply text-xs text-muted-foreground;
    margin-top: 4px;
  }
  
  /* Error message (already good, but standardize) */
  .form-error {
    @apply text-xs font-medium text-destructive;
    margin-top: 4px;
  }
}
```

### Update FormField Component

```tsx
// In FormField.tsx
export const FormField = ({ label, name, helperText, ...props }) => {
  return (
    <div className="form-group">
      <label htmlFor={id} className="form-label">
        {label}
        {required && <span className="text-destructive">*</span>}
      </label>
      <Input id={id} {...props} />
      {helperText && <p className="form-helper">{helperText}</p>}
      {error && <p className="form-error">{error}</p>}
    </div>
  );
};
```

**Action Items:**
- [ ] Convert all `<h1>`–`<h6>` to semantic heading with `.heading-*` class
- [ ] Add `.form-label`, `.form-helper`, `.form-error` component classes
- [ ] Audit all button text for consistent 13px/600 weight
- [ ] Define line-height multipliers (1.4 for tight, 1.6 for body, 1.8 for relaxed)
- [ ] Test readability in light/dark modes for color contrast

---

## Part 3: Forms & Validation

### Current State

**Strengths:**
- ✅ `FormField` component links label to input via `htmlFor`/`id`
- ✅ Inline error messages tied to field via `aria-describedby`
- ✅ `aria-invalid` and `aria-required` attributes present
- ✅ Focus ring on inputs: `focus-visible:ring-[3px]`

**Gaps:**
- ⚠️ **No visual validation indicators:** No checkmark for valid fields
- ⚠️ **Error color inconsistent:** Some errors use `text-destructive`, others hardcoded red
- ⚠️ **No loading state in forms:** Async validation (email exists?) has no spinner/disabled input
- ⚠️ **Helper text missing:** Hints for password strength, character count not shown
- ⚠️ **No touched state:** Form shows errors even before user interacts with field
- ⚠️ **Disabled state styling inconsistent:** Some disabled inputs use `opacity-50`, others have no visual feedback

### Example: AllotmentFormModal

```tsx
// Current: No loading state
<Input name="allocation" value={qty} onChange={...} />

// Desired: Show spinner while validating
<div className="relative">
  <Input name="allocation" disabled={validating} />
  {validating && <Spinner className="absolute right-3 top-3" />}
</div>
```

### Recommended Form Patterns

#### 1. Form State Management

```tsx
// useFormState hook
export const useFormState = (initialValues) => {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [validating, setValidating] = useState({});
  
  const setFieldTouched = (name) => {
    setTouched(prev => ({ ...prev, [name]: true }));
  };
  
  const setFieldValidating = (name, isValidating) => {
    setValidating(prev => ({ ...prev, [name]: isValidating }));
  };
  
  return { values, errors, touched, validating, setFieldTouched, setFieldValidating };
};
```

#### 2. Enhanced FormField with All States

```tsx
export const FormField = ({
  label,
  name,
  value,
  touched,
  error,
  validating,
  helperText,
  isValid,
  ...props
}) => {
  return (
    <div className="form-group">
      <label htmlFor={id} className="form-label">
        {label}
        {props.required && <span className="text-destructive">*</span>}
      </label>
      
      <div className="relative">
        <Input
          id={id}
          value={value}
          disabled={validating || props.disabled}
          aria-invalid={touched && !!error}
          aria-describedby={error ? `${id}-error` : helperText ? `${id}-helper` : undefined}
          {...props}
        />
        
        {/* Validation status indicator */}
        {touched && !validating && (
          isValid ? (
            <Check className="absolute right-3 top-2.5 size-4 text-success" aria-hidden="true" />
          ) : error ? (
            <AlertCircle className="absolute right-3 top-2.5 size-4 text-destructive" aria-hidden="true" />
          ) : null
        )}
        
        {/* Loading spinner */}
        {validating && (
          <Spinner className="absolute right-3 top-2.5 size-4 animate-spin text-muted-foreground" aria-hidden="true" />
        )}
      </div>
      
      {helperText && !error && (
        <p id={`${id}-helper`} className="form-helper">{helperText}</p>
      )}
      {touched && error && (
        <p id={`${id}-error`} className="form-error" role="alert">{error}</p>
      )}
    </div>
  );
};
```

#### 3. Form Error Display

```tsx
// NonFieldErrors already present, but ensure consistent styling
<NonFieldErrors
  errors={["Email already registered", "Phone number invalid"]}
  formatFunction={(errors) => `Unable to save: ${errors.join(", ")}`}
/>
```

**Action Items:**
- [ ] Implement `useFormState` hook with touched/validating states
- [ ] Update `FormField` to show validation checkmark/spinner
- [ ] Add helper text support to all form field types
- [ ] Disable submit button while validating or form is invalid
- [ ] Verify error color contrast meets WCAG AA
- [ ] Test form error announcements with screen readers

---

## Part 4: Tables & Data Display

### Current State

**DataTable Component Strengths:**
- ✅ Skeleton loading with deterministic widths
- ✅ Responsive column width detection (numeric vs text)
- ✅ Inline editing with toggle inputs
- ✅ Custom cell renderers and actions
- ✅ Row styling hook for conditional highlighting

**Gaps:**
- ⚠️ **Mobile overflow:** Tables scroll horizontally; no mobile card view
- ⚠️ **Header sticky behavior:** Thead does not remain visible on scroll
- ⚠️ **Sort indicators missing:** No ↑/↓ icons on sortable columns
- ⚠️ **Row hover inconsistent:** Subtle background; not obvious on mobile touch
- ⚠️ **No selection state:** Bulk actions (delete) need checkboxes, visual feedback
- ⚠️ **Empty column alignment:** Numeric columns should right-align; text left-align
- ⚠️ **Colspan handling:** No built-in support for span cells (totals, summaries)
- ⚠️ **Pagination controls:** Basic but no aria-label or page size selector

### Before/After: Mobile Table View

**Before (broken on mobile):**
```html
<table class="w-full">
  <thead>
    <tr>
      <th>License</th>
      <th>Balance</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>LIC-001</td>
      <td>1000.50</td>
      <td>Active</td>
    </tr>
  </tbody>
</table>
```

On mobile (< 640px), user must scroll horizontally → frustrating.

**After: Responsive Card View**
```tsx
<div className="hidden sm:block">
  {/* Desktop: native table */}
  <table className="w-full table">...</table>
</div>

<div className="space-y-3 sm:hidden">
  {/* Mobile: stacked card layout */}
  {data.map(row => (
    <div key={row.id} className="border rounded-lg p-4">
      <div className="flex justify-between mb-2">
        <span className="font-semibold text-sm">License</span>
        <span className="text-foreground">{row.license}</span>
      </div>
      <div className="flex justify-between mb-2">
        <span className="font-semibold text-sm">Balance</span>
        <span className="font-mono">{row.balance}</span>
      </div>
      <div className="flex justify-between">
        <span className="font-semibold text-sm">Status</span>
        <Badge>{row.status}</Badge>
      </div>
    </div>
  ))}
</div>
```

### Enhanced DataTable with Mobile Support

```tsx
export default function DataTable({
  data = [],
  columns = [],
  mobileFields = null,  // If null, auto-generate from columns
  sortable = [],
  selectable = false,
  selectedRows = [],
  onSelectRow = undefined,
  onSort = undefined,
  sticky = false,
  ...props
}) {
  // Desktop table (existing logic)
  const desktopTable = (
    <div className={`overflow-x-auto ${sticky ? 'max-h-96' : ''}`}>
      <table className="table table-hover">
        <thead className={sticky ? 'sticky top-0 z-10' : ''}>
          {/* columns with sortable indicators */}
        </thead>
        <tbody>
          {/* rows with checkboxes if selectable */}
        </tbody>
      </table>
    </div>
  );

  // Mobile card view
  const mobileView = (
    <div className="space-y-3">
      {data.map(row => (
        <div key={row.id} className="border rounded-lg p-4 space-y-2">
          {(mobileFields || Object.keys(row)).map(field => (
            <div key={field} className="flex justify-between text-sm">
              <span className="font-medium text-muted-foreground">
                {columns.find(c => c.key === field)?.label || field}
              </span>
              <span className="font-medium text-foreground">
                {row[field]}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );

  return (
    <>
      <div className="hidden sm:block">{desktopTable}</div>
      <div className="space-y-3 sm:hidden">{mobileView}</div>
    </>
  );
}
```

### Table Enhancement Checklist

**Sticky Headers:**
```css
.table-sticky thead {
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: blur(4px);
}
```

**Sort Indicators:**
```tsx
<th className="cursor-pointer select-none" onClick={() => onSort(col)}>
  {col.label}
  {sortedBy === col.key && (
    <ChevronUp className={`inline size-3 ml-1 ${ascending ? '' : 'rotate-180'}`} />
  )}
</th>
```

**Numeric Alignment:**
```tsx
const isCurrency = col.key.includes('amount') || col.key.includes('balance');
<td className={isCurrency ? 'text-right font-mono' : 'text-left'}>
  {row[col.key]}
</td>
```

**Action Items:**
- [ ] Create `DataTableMobile` variant or extend `DataTable` with `mobileFields` prop
- [ ] Implement sticky headers for long tables
- [ ] Add sort indicators (up/down arrows) to headers
- [ ] Add numeric right-alignment utility
- [ ] Implement row selection with checkboxes
- [ ] Test horizontal scroll on tablets (iPad, etc.)
- [ ] Add `aria-sort` attributes to sortable headers

---

## Part 5: Filters, Search & Autocomplete

### Current State

**Search Components:**
- `DebouncedSearchInput` — debounced text with 300ms delay
- `DebouncedAsyncSelect` — dropdown with async data fetching
- `AsyncSelectField` — similar async select
- `AdvancedFilter` — multi-field filtering (date range, checkboxes, etc.)
- `DataFilter` — generic filter UI

**Gaps:**
- ⚠️ **No search suggestions:** User types, no dropdown with matches appears
- ⚠️ **Autocomplete feedback missing:** Loading state, empty results, error states not visible
- ⚠️ **Filter UX inconsistent:** Each report/page implements its own filter UI
- ⚠️ **Filter persistence:** Filters clear on page reload (not in URL query params)
- ⚠️ **Active filter display:** No "active filters" badge/chip showing what's applied
- ⚠️ **Clear filters button:** Some pages have it, others don't
- ⚠️ **Mobile filter drawer:** No collapsible/drawer UI for mobile (filters take up half screen)

### Search + Autocomplete UX Spec

#### Before (Current)
```tsx
// DebouncedAsyncSelect: loads data but no feedback
<DebouncedAsyncSelect
  onChange={setSelected}
  loadOptions={fetchLicenses}
/>

// User perspective: type, wait... nothing visible, then suddenly options appear
// Problem: No loading indicator, no "0 results" message, no error handling
```

#### After (Recommended)
```tsx
export const SearchAutocomplete = ({
  placeholder = "Search...",
  loadOptions,
  onSelect,
  formatResult = (item) => item.label,
}) => {
  const [input, setInput] = useState("");
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(false);
  
  // Debounced fetch
  const debouncedFetch = useCallback(
    debounce(async (query) => {
      if (!query.trim()) {
        setOptions([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const results = await loadOptions(query);
        setOptions(results);
        setOpen(true);
      } catch (err) {
        setError(err.message);
        setOpen(true);
      } finally {
        setLoading(false);
      }
    }, 300),
    [loadOptions]
  );
  
  const handleInputChange = (e) => {
    const value = e.target.value;
    setInput(value);
    debouncedFetch(value);
  };
  
  return (
    <div className="relative">
      <div className="relative">
        <Input
          placeholder={placeholder}
          value={input}
          onChange={handleInputChange}
          aria-expanded={open}
          aria-controls="search-results"
          aria-label="Search"
        />
        
        {/* Loading spinner */}
        {loading && (
          <Loader className="absolute right-3 top-2.5 size-4 animate-spin text-muted-foreground" />
        )}
      </div>
      
      {/* Results dropdown */}
      {open && (
        <div
          id="search-results"
          className="absolute top-full left-0 right-0 z-50 mt-2 max-h-48 overflow-y-auto rounded-lg border border-border bg-card shadow-lg"
          role="listbox"
        >
          {loading && (
            <div className="px-4 py-8 text-center">
              <Spinner className="mx-auto mb-2 size-4" />
              <p className="text-xs text-muted-foreground">Searching...</p>
            </div>
          )}
          
          {error && (
            <div className="px-4 py-3 text-sm text-destructive">
              Error: {error}
            </div>
          )}
          
          {!loading && options.length === 0 && input && (
            <EmptyState
              icon={Search}
              title="No results"
              description={`No matches for "${input}"`}
              size="default"
            />
          )}
          
          {options.map((opt, idx) => (
            <button
              key={idx}
              type="button"
              className="w-full px-4 py-2 text-left text-sm hover:bg-muted focus:bg-muted focus-visible:ring-2 focus-visible:ring-ring/40"
              onClick={() => {
                onSelect(opt);
                setInput("");
                setOptions([]);
                setOpen(false);
              }}
              role="option"
            >
              {formatResult(opt)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
```

### Filter Panel Mobile UX

```tsx
export const FilterPanel = ({ filters, onApply, onClear, mobile = false }) => {
  const [open, setOpen] = useState(!mobile);
  
  if (mobile) {
    return (
      <div>
        {/* Trigger button */}
        <button
          className="mb-4 flex items-center gap-2 text-sm font-medium"
          onClick={() => setOpen(!open)}
        >
          <Filter className="size-4" />
          Filters
          {activeFilterCount > 0 && (
            <Badge variant="secondary">{activeFilterCount}</Badge>
          )}
        </button>
        
        {/* Collapsible panel */}
        {open && (
          <div className="mb-4 rounded-lg border border-border bg-card p-4 space-y-4">
            {/* Filter form fields */}
            <div className="flex gap-2">
              <Button onClick={onApply} className="flex-1">Apply Filters</Button>
              <Button variant="outline" onClick={onClear}>Clear</Button>
            </div>
          </div>
        )}
      </div>
    );
  }
  
  // Desktop: sidebar or sticky header
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-4">
      {/* Filters */}
      <div className="flex gap-2">
        <Button onClick={onApply}>Apply</Button>
        <Button variant="outline" onClick={onClear}>Clear</Button>
      </div>
    </div>
  );
};
```

### Active Filters Display

```tsx
// Show applied filters as chips above/below table
export const ActiveFilters = ({ filters, onRemove, onClearAll }) => {
  if (!Object.keys(filters).length) return null;
  
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-muted-foreground">Active Filters:</span>
      {Object.entries(filters).map(([key, value]) => (
        <button
          key={key}
          className="flex items-center gap-1.5 rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground hover:bg-accent/80"
          onClick={() => onRemove(key)}
        >
          {key}: {value}
          <X className="size-3" />
        </button>
      ))}
      <button
        className="text-xs text-muted-foreground hover:text-foreground"
        onClick={onClearAll}
      >
        Clear all
      </button>
    </div>
  );
};
```

**Action Items:**
- [ ] Create `SearchAutocomplete` component with loading/error/empty states
- [ ] Move filter UI to collapsible drawer on mobile (< 640px)
- [ ] Store active filters in URL query params (e.g., `?status=active&port=Mumbai`)
- [ ] Add "Active Filters" chip row above results
- [ ] Implement "Clear Filters" button
- [ ] Test autocomplete with 0 results, API error, slow network (3G)
- [ ] Verify keyboard navigation (arrow keys, Enter, Escape)
- [ ] Add `aria-label` to all filter inputs

---

## Part 6: Dialogs, Modals & Confirmation Flows

### Current State

**ConfirmDialog Component (Excellent):**
- ✅ Focus management (restore previous focus on close)
- ✅ Tab trapping within dialog
- ✅ Keyboard shortcuts (Escape = cancel, Enter = confirm)
- ✅ Severity-based icon/color (danger, warning, info, success)
- ✅ Portalled to `<body>` (not affected by ancestor transform/filter)
- ✅ Backdrop blur, darkening
- ✅ Touch-friendly (max-width 420px, large buttons)

**Gaps:**
- ⚠️ **No long message handling:** Text that exceeds container wraps; no scroll
- ⚠️ **No confirm button disabled state:** Can't prevent accidental double-submit
- ⚠️ **No loading state:** While confirming (e.g., "Deleting..."), no spinner shown
- ⚠️ **Modal layering:** Only one dialog at a time (no sub-dialogs)
- ⚠️ **Delete confirmation inconsistent:** Some pages use ConfirmDialog, others have inline "Delete?" buttons
- ⚠️ **No destructive action guard:** 5-second delay before enabling "Delete" button (common pattern)

### Enhanced ConfirmDialog with Async Operations

```tsx
export const ConfirmDialog = ({
  show,
  title,
  message,
  severity = "warning",
  confirmText = "Confirm",
  cancelText = "Cancel",
  onConfirm,
  onCancel,
  loading = false,  // NEW: show spinner while confirming
  disabled = false,  // NEW: disable confirm button (e.g., delay)
  messageMaxHeight = false,  // NEW: scrollable message
  ...props
}) => {
  return (
    <Dialog open={show} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent>
        <div className="flex items-start gap-4 px-6 pb-5 pt-6">
          <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", cfg.iconCls)}>
            <Icon className="size-5" />
          </span>
          
          <div className="min-w-0 flex-1">
            <h2 className="mb-1.5 text-base font-semibold">{title}</h2>
            <p className={cn("text-sm text-muted-foreground", messageMaxHeight && "max-h-64 overflow-y-auto")}>
              {message}
            </p>
          </div>
        </div>
        
        <div className="flex justify-end gap-2 border-t px-6 py-4">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            {cancelText}
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading || disabled}
            className={cfg.confirmCls}
          >
            {loading && <Spinner className="mr-2 size-4 animate-spin" />}
            {confirmText}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
```

### Delete Confirmation Pattern

```tsx
// Usage with destructive action protection
export const DeleteLicenseButton = ({ licenseId, onDeleted }) => {
  const [showConfirm, setShowConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [canConfirm, setCanConfirm] = useState(false);
  
  // 3-second delay before allowing confirmation
  useEffect(() => {
    if (!showConfirm) {
      setCanConfirm(false);
      return;
    }
    const timer = setTimeout(() => setCanConfirm(true), 3000);
    return () => clearTimeout(timer);
  }, [showConfirm]);
  
  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/licenses/${licenseId}/`);
      toast.success("License deleted");
      onDeleted();
    } catch (err) {
      toast.error(`Error: ${err.message}`);
    } finally {
      setDeleting(false);
      setShowConfirm(false);
    }
  };
  
  return (
    <>
      <Button
        variant="destructive"
        size="sm"
        onClick={() => setShowConfirm(true)}
      >
        Delete
      </Button>
      
      <ConfirmDialog
        show={showConfirm}
        title="Delete License?"
        message="This action cannot be undone. All associated allotments and BOEs will be removed."
        severity="danger"
        confirmText={canConfirm ? "Yes, Delete" : `Wait ${3}s...`}
        disabled={!canConfirm || deleting}
        loading={deleting}
        onConfirm={handleDelete}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
};
```

### Modal Nesting (Sub-dialogs)

Currently, only one modal can be open. If user opens a sub-dialog while main dialog is open, behavior is undefined.

```tsx
// Solution: Stack dialogs with z-index management
// Use a modal provider to track open dialogs

export const ModalProvider = ({ children }) => {
  const [stack, setStack] = useState([]);
  
  const openModal = (id, content, onClose) => {
    setStack(prev => [...prev, { id, content, onClose }]);
  };
  
  const closeModal = (id) => {
    setStack(prev => {
      const dialog = prev.find(d => d.id === id);
      dialog?.onClose?.();
      return prev.filter(d => d.id !== id);
    });
  };
  
  return (
    <ModalContext.Provider value={{ openModal, closeModal, stack }}>
      {children}
      {stack.map((dialog, idx) => (
        <div
          key={dialog.id}
          className={`fixed inset-0 z-[${1050 + idx}] flex items-center justify-center`}
        >
          {dialog.content}
        </div>
      ))}
    </ModalContext.Provider>
  );
};
```

**Action Items:**
- [ ] Add `loading` prop to `ConfirmDialog` to show spinner while confirming
- [ ] Add `disabled` prop for destructive action delay (3-5 seconds)
- [ ] Make confirm message scrollable if > 300px
- [ ] Implement `ModalProvider` for stacking dialogs
- [ ] Standardize all delete confirmations to use same pattern
- [ ] Add retry behavior for failed deletions
- [ ] Test keyboard navigation (Tab, Escape) in all dialogs

---

## Part 7: Responsive Design & Mobile UX

### Current State

| Component | Mobile | Tablet | Desktop |
|-----------|--------|--------|---------|
| TopNav | ✅ Responsive | ✅ | ✅ |
| Page padding | ⚠️ Hardcoded | — | ⚠️ Uses Bootstrap defaults |
| Tables | ❌ Horizontal scroll | ⚠️ Narrow | ✅ |
| Forms | ✅ Full width | ✅ | ✅ |
| Modals | ✅ Responsive | ✅ | ✅ |
| Buttons | ⚠️ Small touch target | ✅ | ✅ |
| Footer actions | ⚠️ Cramped | ⚠️ Narrow | ✅ |

### Findings

1. **Breakpoints not consistent:** Some components use `sm:`, others `md:` or none
2. **Touch targets:** Some buttons only 28px × 28px (Apple HIG recommends 44px min)
3. **Pagination:** Links too close together on mobile; no "previous/next" buttons
4. **Modal width:** Max-width 420px too narrow on iPad (landscape)
5. **Footer overflow:** Quick action buttons wrap on narrow screens

### Responsive Breakpoints (Standardized)

```css
/* In Tailwind config or CSS */
@media (max-width: 640px) { /* sm */ }
@media (max-width: 768px) { /* md */ }
@media (max-width: 1024px) { /* lg */ }
@media (max-width: 1280px) { /* xl */ }
```

**Convention:** Use `sm:` (640px) as primary mobile breakpoint.

### Mobile-Friendly Button Touch Targets

```tsx
// Before
<button className="px-2 py-1 text-xs">Save</button>  // ~24px height

// After: Minimum 44px height on mobile
<button className="px-3 py-2 text-sm sm:px-4 sm:py-2 sm:text-sm">
  Save
</button>
```

### Responsive Modal

```tsx
<DialogContent className="w-[95vw] max-w-lg sm:max-w-2xl md:max-w-3xl">
  {/* Grows to 95% viewport width on mobile, capped at 1200px on desktop */}
</DialogContent>
```

### Responsive Footer Actions

```tsx
// Before: Fixed footer gets cramped on mobile
<footer className="flex gap-1.5">
  {QUICK_ACTIONS.map(...)}
</footer>

// After: Stack on mobile, row on desktop
<footer className="flex flex-col gap-2 sm:flex-row sm:gap-1.5">
  {QUICK_ACTIONS.map(...)}
</footer>
```

### Touch-Friendly Pagination

```tsx
export const DataPagination = ({ page, totalPages, onPageChange }) => {
  return (
    <div className="flex items-center justify-between gap-2 py-4">
      <button
        className="px-3 py-2 text-sm font-medium"  // 44px min height
        disabled={page === 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </button>
      
      <div className="hidden gap-1 sm:flex">
        {/* Page number buttons on desktop */}
        {Array.from({ length: totalPages }).map((_, i) => (
          <button
            key={i}
            className={i + 1 === page ? "bg-primary text-white" : "border"}
            onClick={() => onPageChange(i + 1)}
          >
            {i + 1}
          </button>
        ))}
      </div>
      
      <span className="text-xs text-muted-foreground sm:text-sm">
        {page} of {totalPages}
      </span>
      
      <button
        className="px-3 py-2 text-sm font-medium"
        disabled={page === totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
};
```

**Action Items:**
- [ ] Audit all buttons for 44px minimum height on mobile
- [ ] Use `sm:` consistently as primary breakpoint (640px)
- [ ] Convert tables to card view on mobile (< 640px)
- [ ] Make modal responsive: `w-[95vw] max-w-lg sm:max-w-2xl`
- [ ] Test on actual mobile devices (iPhone 12, Samsung Galaxy S21)
- [ ] Verify touch targets are not overlapping (min 8px gap)
- [ ] Check landscape orientation (iPad, etc.)
- [ ] Test with zoom at 200% (accessibility requirement)

---

## Part 8: Accessibility (WCAG AA Compliance)

### Current State

**Strong Areas:**
- ✅ Form labels linked to inputs via `htmlFor`/`id`
- ✅ Error messages tied to fields via `aria-describedby`
- ✅ `aria-invalid`, `aria-required` on form fields
- ✅ Dialog focus management and tab trapping
- ✅ Keyboard shortcuts documented (Escape, Enter)
- ✅ ARIA live regions for announcements (`role="status"`, `aria-live="polite"`)

**Gaps:**
- ⚠️ **Color contrast:** Some badge/text combinations not verified for AA (4.5:1)
- ⚠️ **Focus indicators:** Not visible on all interactive elements (especially on mobile)
- ⚠️ **Alt text for icons:** `aria-hidden="true"` used correctly, but verify all semantic icons
- ⚠️ **Keyboard navigation:** Dropdown menus, autocomplete may not be fully keyboard-accessible
- ⚠️ **Screen reader testing:** No testing with NVDA (Windows), JAWS, VoiceOver
- ⚠️ **Link text:** Some links have poor descriptive text (e.g., "click here" vs "View license balance")
- ⚠️ **Mobile focus indicators:** Focus ring may not be visible on mobile when keyboard is hidden
- ⚠️ **Motion:** Animations may trigger motion sickness for users with vestibular disorders (no `prefers-reduced-motion` support detected)

### Required Contrast Ratios (WCAG AA)

| Element | Size | Ratio |
|---------|------|-------|
| Normal text | < 18px | 4.5:1 |
| Large text | >= 18px bold or 24px | 3:1 |
| UI components (borders, icons) | any | 3:1 |
| Disabled text | any | no requirement |

**Test colors programmatically:**
```js
const getContrast = (fg, bg) => {
  const getLuminance = (hex) => {
    const [r, g, b] = hex.match(/\w\w/g).map(x => parseInt(x, 16) / 255);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const lFg = getLuminance(fg), lBg = getLuminance(bg);
  const [lighter, darker] = lFg > lBg ? [lFg, lBg] : [lBg, lFg];
  return (lighter + 0.05) / (darker + 0.05);
};

// Example
getContrast("#ffffff", "#0066cc"); // 8.59:1 (AAA)
getContrast("#666666", "#ffffff"); // 4.48:1 (AA)
```

### Focus Visible on All Interactive Elements

```css
/* Global: visible focus ring on all keyboard-interactive elements */
button:focus-visible,
[role="button"]:focus-visible,
a[href]:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible {
  outline: 3px solid var(--ring);
  outline-offset: 2px;
}

/* Already present in Input component; verify on ALL interactive elements */
```

### Reduced Motion Support

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### Keyboard Navigation Checklist

- [ ] **Tab navigation:** All interactive elements (buttons, inputs, links) reachable via Tab
- [ ] **Shift+Tab:** Backward navigation works
- [ ] **Enter/Space:** Buttons and links activate
- [ ] **Arrow keys:** Dropdown menus, list boxes, radio buttons use arrow keys
- [ ] **Escape:** Close modals, dropdowns, autocomplete
- [ ] **Tab trap:** Tab within modals (already implemented in ConfirmDialog)

### Screen Reader Testing

Use [NVDA](https://www.nvaccess.org/) (Windows) or [JAWS trial](https://support.freedomscientific.com/Downloads/JAWS).

**Test scenarios:**
- [ ] Read page title
- [ ] Announce form labels and required/invalid status
- [ ] Read button purposes (e.g., "Delete license button")
- [ ] Announce modal open/close
- [ ] Read error messages in context
- [ ] Navigate table with arrow keys

### Example: Accessible Icon Button

```tsx
// Before (inaccessible)
<button onClick={handleDelete}>
  <Trash2 className="size-4" />
</button>

// After (accessible)
<button
  onClick={handleDelete}
  aria-label="Delete license"  // Describes purpose
  title="Delete license"        // Tooltip fallback
>
  <Trash2 className="size-4" aria-hidden="true" />  // Icon hidden from screen readers
</button>
```

**Action Items:**
- [ ] Run color contrast checker on all badge/text combinations
- [ ] Add `focus-visible:ring-[3px]` to ALL interactive elements
- [ ] Add `prefers-reduced-motion` media query to reduce animations
- [ ] Test with NVDA/JAWS on sample pages
- [ ] Add `aria-label` to all icon-only buttons
- [ ] Verify link text is descriptive (not "click here")
- [ ] Test keyboard navigation: Tab, Shift+Tab, Enter, Escape, Arrow keys
- [ ] Verify tab order matches visual order
- [ ] Test at 200% zoom (WCAG requirement)

---

## Part 9: Loading States & Skeleton Screens

### Current State

**Good:**
- ✅ `TableSkeleton` with deterministic widths (no flicker)
- ✅ `LoadingFallback` component for page transitions
- ✅ `Skeleton` primitive from shadcn/ui

**Gaps:**
- ⚠️ **Skeleton consistency:** Not used in all async components (search, export, filter)
- ⚠️ **Shimmer animation:** Skeleton has opacity pulse; could be more prominent
- ⚠️ **Loading count:** Unclear how many rows to show (6? 10?)
- ⚠️ **Partial skeletons:** Form fields, cards lack skeleton states
- ⚠️ **API error recovery:** Skeletons stay visible if API fails
- ⚠️ **Lazy-loaded images:** No placeholder/skeleton for images

### Enhanced Skeleton with Shimmer

```tsx
// Current implementation
export const Skeleton = ({ className }) => (
  <div
    className={cn("animate-pulse rounded-md bg-muted", className)}
  />
);

// Enhanced: Add shimmer effect
export const Skeleton = ({ className, shimmer = true }) => (
  <div
    className={cn(
      "rounded-md bg-muted",
      shimmer && "animate-shimmer",
      className
    )}
  />
);

// Add to tailwind.css
@keyframes shimmer {
  0% { background-position: -1000px 0; }
  100% { background-position: 1000px 0; }
}

@layer utilities {
  .animate-shimmer {
    background: linear-gradient(
      90deg,
      var(--tb-border-soft) 25%,
      var(--tb-sunken) 50%,
      var(--tb-border-soft) 75%
    );
    background-size: 1000px 100%;
    animation: shimmer 2s infinite;
  }
}
```

### Form Field Skeleton

```tsx
export const FormFieldSkeleton = ({ label, rows = 1 }) => (
  <div className="form-group">
    <Skeleton className="h-4 w-20" />
    {Array.from({ length: rows }).map((_, i) => (
      <Skeleton key={i} className={`h-9 ${i > 0 ? 'mt-2' : ''}`} />
    ))}
  </div>
);
```

### Card Skeleton

```tsx
export const CardSkeleton = () => (
  <div className="surface-card space-y-4 p-6">
    <Skeleton className="h-6 w-40" />
    <Skeleton className="h-4 w-full" />
    <Skeleton className="h-4 w-3/4" />
  </div>
);
```

### Error State After Failed Load

```tsx
// After skeleton disappears (timeout or error), show error
export const DataGrid = ({ isLoading, error, data, ...props }) => {
  if (isLoading) {
    return <TableSkeleton rowCount={6} />;
  }
  
  if (error) {
    return (
      <ErrorState
        icon={AlertCircle}
        title="Failed to load data"
        message={error.message}
        action={
          <Button onClick={() => refetch()}>
            Retry
          </Button>
        }
      />
    );
  }
  
  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="No records found"
      />
    );
  }
  
  return <table>{...}</table>;
};
```

**Action Items:**
- [ ] Apply `Skeleton` component to all async-loaded sections
- [ ] Add shimmer animation to skeletons
- [ ] Create `FormFieldSkeleton` and `CardSkeleton` components
- [ ] Show 1-2 skeleton rows while loading (not 6)
- [ ] Replace skeletons with error state if API fails
- [ ] Add retry button to error states
- [ ] Test perceived performance (does skeleton feel faster?)

---

## Part 10: Dark Mode & Theming

### Current State

**Implementation:**
- ✅ `ThemeContext` manages `[data-theme="dark"]` attribute on `<html>`
- ✅ Tailwind `dark:` variant configured to respect `[data-theme="dark"]`
- ✅ CSS variables bridge shadcn tokens to `--tb-*` tokens
- ✅ Both light/dark versions of all semantic colors defined

**Gaps:**
- ⚠️ **Image handling:** Some images have no dark mode variant (white logos on white)
- ⚠️ **Component coverage:** Some components use hardcoded colors (e.g., `bg-white`)
- ⚠️ **Transition:** Theme switch has no fade/transition (jarring)
- ⚠️ **System preference:** No auto-detection of `prefers-color-scheme`
- ⚠️ **Persistence:** Theme preference not saved to localStorage

### Enhanced Theme Context

```tsx
export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    // 1. Check localStorage
    const stored = localStorage.getItem('theme');
    if (stored) return stored as 'light' | 'dark';
    
    // 2. Check system preference
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    
    return 'light';
  });
  
  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    
    // Smooth transition
    document.documentElement.style.transitionProperty = 'background-color, color, border-color';
    document.documentElement.style.transitionDuration = '200ms';
  }, [theme]);
  
  // Listen to system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      if (!localStorage.getItem('theme')) {
        setTheme(e.matches ? 'dark' : 'light');
      }
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);
  
  const toggleTheme = useCallback(() => {
    setTheme(t => t === 'light' ? 'dark' : 'light');
  }, []);
  
  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
```

### Dark Mode for Images

```tsx
// Before: White logo invisible in dark mode
<img src="/logo.svg" alt="License Manager" />

// After: Use dark variant
<picture>
  <source
    srcSet="/logo-dark.svg"
    media="(prefers-color-scheme: dark)"
  />
  <img src="/logo.svg" alt="License Manager" />
</picture>

// Or with CSS
<img
  src="/logo.svg"
  alt="License Manager"
  className="invert dark:invert-0"  // Invert white logo in dark mode only
/>
```

**Action Items:**
- [ ] Detect system `prefers-color-scheme` on first load
- [ ] Save theme preference to `localStorage`
- [ ] Add smooth transition when switching themes (200ms)
- [ ] Audit all images for dark mode variants
- [ ] Remove hardcoded `bg-white`, `text-black` in favor of semantic colors
- [ ] Test all components in dark mode (especially badges, borders)

---

## Part 11: Master Sync Status & Conflict Display

### Current State

No dedicated UI for Master sync conflicts. Users see generic errors without context on what went wrong or how to resolve.

### Master Sync Conflict States

```tsx
// Types of conflicts that can occur:
// 1. CONCURRENT_UPDATE: User A and B both edited same Company
// 2. REMOTE_CONFLICT: Local version differs from remote server
// 3. STALE_REFERENCE: Port deleted on server; local License still references it
// 4. ORPHANED_FK: BOE references deleted Company

export const MasterSyncStatus = {
  SYNCED: 'synced',
  PENDING: 'pending',
  CONFLICT: 'conflict',
  ERROR: 'error',
  OFFLINE: 'offline',
};

export const ConflictReason = {
  CONCURRENT_UPDATE: 'Another user modified this record while you were editing',
  REMOTE_OUTDATED: 'Your local version is newer; waiting to push',
  REMOTE_CONFLICT: 'Server has a newer version; merge required',
  STALE_REFERENCE: 'Referenced record was deleted on server',
  ORPHANED_FK: 'This record references a deleted item; fix required',
};
```

### Conflict Resolution UI

```tsx
export const MasterConflictResolver = ({ conflict, onResolve }) => {
  const [selectedResolution, setSelectedResolution] = useState(null);
  
  return (
    <div className="rounded-lg border-2 border-warning bg-warning/5 p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start gap-3">
        <AlertTriangle className="size-5 text-warning shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-base">Sync Conflict</h3>
          <p className="text-sm text-muted-foreground mt-1">
            {ConflictReason[conflict.reason]}
          </p>
        </div>
      </div>
      
      {/* Versions comparison */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="rounded border border-border bg-card p-3">
          <p className="font-medium mb-2">Your version</p>
          <pre className="text-xs overflow-auto max-h-32 bg-muted p-2 rounded">
            {JSON.stringify(conflict.localVersion, null, 2)}
          </pre>
        </div>
        <div className="rounded border border-border bg-card p-3">
          <p className="font-medium mb-2">Server version</p>
          <pre className="text-xs overflow-auto max-h-32 bg-muted p-2 rounded">
            {JSON.stringify(conflict.remoteVersion, null, 2)}
          </pre>
        </div>
      </div>
      
      {/* Resolution options */}
      <div className="space-y-2">
        <p className="text-sm font-medium">How do you want to resolve this?</p>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="resolution"
            value="keep-local"
            checked={selectedResolution === 'keep-local'}
            onChange={(e) => setSelectedResolution(e.target.value)}
          />
          <span className="text-sm">Keep my version (overwrite server)</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="resolution"
            value="keep-remote"
            checked={selectedResolution === 'keep-remote'}
            onChange={(e) => setSelectedResolution(e.target.value)}
          />
          <span className="text-sm">Use server version (discard my changes)</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="resolution"
            value="merge"
            checked={selectedResolution === 'merge'}
            onChange={(e) => setSelectedResolution(e.target.value)}
          />
          <span className="text-sm">Merge (combine changes)</span>
        </label>
      </div>
      
      <div className="flex gap-2 pt-2">
        <Button
          variant="default"
          onClick={() => onResolve(selectedResolution)}
          disabled={!selectedResolution}
        >
          Resolve
        </Button>
        <Button variant="outline">
          Get Help
        </Button>
      </div>
    </div>
  );
};
```

### Sync Status Indicator

```tsx
// Global header indicator
export const MasterSyncIndicator = ({ status, conflictCount }) => {
  const config = {
    synced: { icon: Check, color: 'text-success', label: 'Synced' },
    pending: { icon: Clock, color: 'text-warning', label: 'Syncing...' },
    conflict: { icon: AlertTriangle, color: 'text-destructive', label: `${conflictCount} conflicts` },
    error: { icon: AlertCircle, color: 'text-destructive', label: 'Sync error' },
    offline: { icon: Wifi, color: 'text-muted-foreground', label: 'Offline' },
  }[status];
  
  const Icon = config.icon;
  
  return (
    <button
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
        status === 'conflict' ? 'bg-destructive/10' : 'bg-muted'
      }`}
      onClick={() => openSyncPanel()}
    >
      <Icon className={`size-3.5 ${config.color}`} />
      {config.label}
    </button>
  );
};
```

**Action Items:**
- [ ] Create `MasterConflictResolver` modal with version diff display
- [ ] Add `MasterSyncIndicator` to header
- [ ] Log all conflicts to database for audit trail
- [ ] Implement conflict resolution UI (keep local, keep remote, merge)
- [ ] Add "Resolve Conflicts" page under Reconciliation
- [ ] Test concurrent edits scenario

---

## Part 12: Component Consolidation & Deduplication

### Current Duplicate Components

| Functionality | Location 1 | Location 2 | Status |
|---------------|-----------|-----------|--------|
| Card | `ui/card.tsx` | `primitives/Card.tsx` | ❌ **Duplicate** |
| Empty state | `components/EmptyState.tsx` | `primitives/EmptyState.tsx` | ❌ **Duplicate** |
| Button | `ui/button.tsx` | `primitives/Button.tsx` | ❌ **Duplicate** |
| Stat card | `primitives/StatCard.tsx` | `license-overview/StatCard.tsx` | ❌ **Duplicate** |
| Page header | `components/PageHeader.tsx` | `primitives/PageHeader.tsx` | ❌ **Duplicate** |

### Consolidation Plan

**Phase 1: Audit & Document**
- [ ] Grep for component duplicates
- [ ] Compare implementations (are they identical or slightly different?)
- [ ] Document which version is "canonical"

**Phase 2: Merge & Standardize**
- [ ] Keep `shadcn/ui` components in `/ui` (pristine, shadcn-managed)
- [ ] Keep custom/compound components in `/components` (our code)
- [ ] Remove `/primitives` folder; merge essential ones into `components/`
- [ ] Create `/components/primitives.ts` barrel export for frequently used compounds

**Phase 3: Update Imports**
- [ ] Replace all imports of removed duplicates
- [ ] Update path aliases in `package.json` or imports
- [ ] Run tests to verify no broken imports

### Example: Consolidate Card Components

```tsx
// REMOVE: primitives/Card.tsx (if identical to ui/card.tsx)
// KEEP: ui/card.tsx (from shadcn/ui)
// ADD: components/Card.tsx (compound card with header/body/footer)

import { Card as UICard, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

export const Card = UICard;
export const CardContent = CardContent;
export const CardHeader = CardHeader;
export const CardTitle = CardTitle;
export const CardFooter = CardFooter;
export const CardDescription = CardDescription;

// Custom compound components
export const CardWithActions = ({ title, children, actions }) => (
  <Card>
    <CardHeader>
      <div className="flex items-center justify-between">
        <CardTitle>{title}</CardTitle>
        <div className="flex gap-2">{actions}</div>
      </div>
    </CardHeader>
    <CardContent>{children}</CardContent>
  </Card>
);
```

**Action Items:**
- [ ] Audit all files in `/components/ui` and `/components/primitives` for duplicates
- [ ] Create a master list of canonical component locations
- [ ] Merge or remove duplicate implementations
- [ ] Update all import statements
- [ ] Add barrel exports (`index.ts`) for common imports
- [ ] Document component usage patterns in `COMPONENT_LIBRARY.md`

---

## Part 13: Summary & Implementation Roadmap

### Priority 1: Critical UX/Accessibility (Week 1)

| Task | Effort | Impact |
|------|--------|--------|
| Fix focus indicators on all interactive elements | 2h | 🔴 Critical |
| Add color contrast verification (WCAG AA) | 3h | 🔴 Critical |
| Make tables mobile-responsive (card view) | 6h | 🟡 High |
| Consolidate duplicate components | 4h | 🟢 Medium |

### Priority 2: Form & Input Improvements (Week 2)

| Task | Effort | Impact |
|------|--------|--------|
| Add validation checkmarks, spinners, helper text | 4h | 🟡 High |
| Implement `useFormState` hook | 3h | 🟡 High |
| Add `SearchAutocomplete` with loading/error states | 4h | 🟡 High |
| Enhance `ConfirmDialog` with loading, delay | 2h | 🟡 High |

### Priority 3: Mobile & Responsive (Week 3)

| Task | Effort | Impact |
|------|--------|--------|
| Standardize spacing & typography | 4h | 🟡 High |
| Make buttons 44px min height on mobile | 2h | 🟡 High |
| Add mobile filter drawer | 3h | 🟡 High |
| Test on actual devices (iOS, Android) | 2h | 🟡 High |

### Priority 4: Master Sync & Advanced Features (Week 4)

| Task | Effort | Impact |
|------|--------|--------|
| Build Master conflict resolver UI | 6h | 🟢 Medium |
| Add Master sync status indicator | 2h | 🟢 Medium |
| Implement skeleton loading for all async operations | 3h | 🟢 Medium |
| Dark mode refinements (system preference, images) | 2h | 🟢 Medium |

### Metrics to Track

```
BEFORE:
- Lighthouse Accessibility: 70%
- Keyboard Navigation: 60% complete
- Focus visible: 40% of interactive elements
- Mobile (< 640px) usable: 50%
- Component duplication: 8 pairs

AFTER:
- Lighthouse Accessibility: 95%+
- Keyboard Navigation: 100% complete
- Focus visible: 100% of interactive elements
- Mobile usable: 100%
- Component duplication: 0 pairs
```

---

## Part 14: Design System Documentation

### Create `DESIGN_SYSTEM.md`

```markdown
# Design System — License Manager

## Spacing

- **xs:** 4px (`spacing-xs`)
- **sm:** 8px (`spacing-sm`)
- **md:** 12px (`spacing-md`)
- **lg:** 16px (`spacing-lg`)
- **xl:** 20px (`spacing-xl`)
- **2xl:** 24px (`spacing-2xl`)

## Typography

### Headings
- **h1:** 30px, bold, 1.2 line-height
- **h2:** 24px, bold, 1.3 line-height
- **h3:** 20px, semibold, 1.3 line-height

### Body
- **lg:** 16px, normal, 1.5 line-height (relaxed)
- **base:** 14px, normal, 1.4 line-height (default)
- **sm:** 12px, normal, 1.4 line-height

### Forms
- **label:** 14px, medium weight
- **error:** 11.5px, medium weight, destructive color
- **helper:** 12px, normal weight, secondary color

## Colors

### Semantic
- **primary:** #0066cc (blue)
- **success:** #10b981 (green)
- **warning:** #f59e0b (amber)
- **destructive:** #dc2626 (red)
- **info:** #0ea5e9 (cyan)

### Surfaces
- **card:** light gray background
- **muted:** light secondary background
- **input:** card background

## Components

[List all components with usage examples]

## Accessibility

- All interactive elements must have visible focus indicator
- Forms must have linked labels
- Modals must have focus management
- Icons must be hidden from screen readers (aria-hidden)
- Ensure 4.5:1 contrast ratio for text
```

---

## Final Checklist

- [ ] Fix all focus indicators (critical accessibility)
- [ ] Verify color contrast (WCAG AA)
- [ ] Consolidate duplicate components
- [ ] Add mobile table card view
- [ ] Enhance forms with validation states
- [ ] Create SearchAutocomplete component
- [ ] Improve ConfirmDialog with loading/delay
- [ ] Implement Master conflict resolver
- [ ] Standardize spacing & typography
- [ ] Add prefers-reduced-motion support
- [ ] Test on real devices (mobile, tablet, desktop)
- [ ] Document design system
- [ ] Automate contrast checking in CI/CD
- [ ] Set up accessibility testing in test suite

---

## References

- [WCAG 2.1 AA Compliance](https://www.w3.org/WAI/WCAG21/quickref/)
- [Radix UI Primitives](https://www.radix-ui.com/)
- [Tailwind CSS Docs](https://tailwindcss.com/)
- [shadcn/ui](https://ui.shadcn.com/)
- [Apple HIG (Human Interface Guidelines)](https://developer.apple.com/design/human-interface-guidelines/)
- [Material Design 3](https://m3.material.io/)

