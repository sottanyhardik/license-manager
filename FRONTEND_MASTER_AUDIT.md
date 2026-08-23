# Frontend Master Selector Audit

**Audited Date:** August 12, 2026  
**Scope:** Frontend Master usage across all UI Master selectors, autocomplete, dropdowns, search, and CRUD pages  
**Coverage:** All 14 Master entities and their frontend integration points

---

## Executive Summary

The frontend uses Master data through **3 primary selector components** (AsyncSelectField, HybridSelect, DebouncedAsyncSelect) integrated across **7+ pages/modals** and **2 report filters**. All selectors correctly route to the backend Master APIs, with proper caching, debouncing, and error handling. Minor gaps exist in loading state indicators for some filters and no explicit "deleted Master" recovery patterns.

### Key Findings
- ✅ All 14 Master API endpoints properly configured in backend
- ✅ Frontend selectors use correct endpoints with proper field mappings
- ✅ Debouncing, caching, and recent-selections implemented
- ✅ Multi-select and single-select patterns both supported
- ⚠️ Inconsistent error messaging across filters (some silent, some toast)
- ⚠️ No explicit "Master deleted after selection" recovery
- ⚠️ Pagination not visible in dropdown menus (50-item limit)
- ⚠️ Stale selection handling relies on API 404 fallback

---

## Master Coverage Matrix

| Master Entity | Endpoint | Frontend Pages | Selector Type | Status |
|---|---|---|---|---|
| **Company** | `masters/companies/` | MasterForm, TradeForm, AllotmentAction, AllotmentFilters, ItemPivot, ItemReport, LicensePurchaseProfit, LicenseLedger | AsyncSelectField + HybridSelect | ✅ Complete |
| **Port** | `masters/ports/` | AllotmentFormModal, MasterForm (via metadata) | HybridSelect | ✅ Complete |
| **HS Code** | `masters/hs-codes/` | MasterForm (via metadata), HybridSelect | HybridSelect | ✅ Complete |
| **SION Norm Class** | `masters/sion-classes/` | MasterForm, AllotmentFilters, LicenseLedger, InlineNormEditor, ItemPivot, ItemReport | AsyncSelectField + HybridSelect | ✅ Complete |
| **Head SION Norms** | `masters/head-norms/` | MasterForm (metadata only) | Not directly used in UI | ✅ Minimal |
| **Item Name** | `masters/item-names/` | LicenseBalanceModal, LedgerTab (read-only display) | AsyncSelect (API call, not component) | ✅ Read-only |
| **Product Description** | `masters/product-descriptions/` | NestedFieldArray (item import) | AsyncSelect (API call) | ✅ Minimal |
| **Exchange Rate** | `masters/exchange-rates/` | AllotmentFormModal, MasterForm | HybridSelect | ✅ Complete |
| **Transfer Letter** | `masters/transfer-letters/` | TransferLetterForm, MasterForm | AsyncSelectField | ✅ Complete |
| **Purchase Status** | `masters/purchase-statuses/` | MasterForm, LicenseLedger, ItemPivot, LicensePurchaseProfit | usePurchaseStatusOptions hook + HybridSelect | ✅ Complete |
| **Scheme Code** | `masters/scheme-codes/` | MasterForm (via metadata) | HybridSelect | ✅ Complete |
| **Notification Number** | `masters/notification-numbers/` | AllotmentAction, useItemReportFilters (read-only) | AsyncSelect (API call) | ✅ Minimal |
| **Group** | `masters/groups/` | MasterForm (metadata only) | Not directly used in UI | ✅ Minimal |
| **Unit Price** | `masters/unit-prices/` | Not used in UI selectors | — | ⚠️ Backend only |

---

## Component Deep Dive

### 1. AsyncSelectField Component
**File:** `frontend/src/components/AsyncSelectField.tsx`

#### Features Implemented ✅
- **Search:** Debounced API search with regex-safe query escaping
- **Caching:** FK detail cache (`_fkDetailCache`) + in-flight request deduplication
- **Recent Selections:** Session-scoped storage of last 5 picks (via sessionStorage)
- **Loading:** Spinner indicator during search (250ms debounce delay, configurable)
- **Multi-select:** Full support with array handling
- **Labels:** Custom formatting with optional subtitle line in dropdown
- **Error Recovery:** Silently returns empty array on API 404/error

#### Edge Cases Handled ✅
- Numeric vs. slug-based IDs (non-numeric IDs bypass detail endpoint)
- Comma-separated value parsing for backward compatibility
- Empty query handling (shows recent selections instead of empty menu)
- Highlight matching with case-insensitive regex

#### Gaps Identified ⚠️
- **No explicit "Master deleted" recovery:** If a Master is deleted after selection, clicking the field again and clearing/reselecting is the only recovery. No warning displayed.
- **Silent error handling:** Network errors return empty array — no user feedback (relies on app-level error boundaries)
- **No pagination indicators:** Menu caps at 50 items; no "load more" or notification visible
- **Stale selection display:** If selected Master was deleted, displays cached label until next re-render

### 2. HybridSelect Component
**File:** `frontend/src/components/HybridSelect.tsx`

#### Pattern ✅
- Intelligently routes to AsyncSelectField if `endpoint` is provided, else static Select
- Supports both FK lookups (`fk_endpoint`) and direct endpoints
- Custom format label logic for HS Code and Port fields

#### Integration Points ✅
- MasterForm: All FK fields (Company, Port, HS Code, etc.)
- TradeForm: Inline company/bill-of-entry pickers
- AllotmentFormModal: Port, Exchange Rate selection
- IncentiveLicenses: Company and license link

#### Gaps Identified ⚠️
- **Special-case label logic only for HS Code/Port:** Other Masters use generic `item[labelField]` fallback
- **No validation of deleted selections:** If a FK Master was deleted server-side, form accepts stale selection until submit

### 3. DebouncedAsyncSelect Component
**File:** `frontend/src/components/DebouncedAsyncSelect.tsx`

#### Usage ⚠️ Limited — only in AdvancedFilter for generic Master searches

#### Features ✅
- Debounce delay configurable (default 300ms)
- Searching spinner
- Cache options support

#### Gap ⚠️
- Less sophisticated than AsyncSelectField (no recent selections, no FK cache deduplication)

### 4. usePurchaseStatusOptions Hook
**File:** `frontend/src/hooks/useMasterOptions.ts`

#### Pattern ✅
- Module-scoped cache for shared master lists (purchase statuses, SION norms)
- Single network request per session, results shared across all components
- Filters: `is_active=true`, sorted by backend's declared `display_order`

#### Used By ✅
- ItemPivotFilters
- LicenseLedger filters
- Any page showing Purchase Status multi-select

#### Strength ✅
- Ensures consistent ordering and active/inactive filtering across entire app
- Never shows inactive Norms (filtered at fetch, not on UI)

---

## Frontend Master Selector Locations

### Master CRUD Pages
| Page | Path | Masters Used | Selector Type |
|---|---|---|---|
| Master List/Search | `/masters/:entity` | All 14 | Mixed (read-only list + edit links) |
| Master Form (Create/Edit) | `/masters/:entity/create`, `/masters/:entity/:id/edit` | All via metadata | HybridSelect |
| License Form | `/licenses/create`, `/licenses/:id/edit` | Company, Port, Exchange Rate, SION, Purchase Status | HybridSelect |
| Allotment Form | `/allotments/create`, `/allotments/:id/edit` | Company, Port, Exchange Rate, Scheme | HybridSelect |
| BOE Form | `/bill-of-entries/create`, `/bill-of-entries/:id/edit` | Company, Port, Exchange Rate | HybridSelect |
| Trade Form | `/trades/create`, `/trades/:id/edit` | Company (multiple), Invoice FK, License Item FK | HybridSelect |
| Incentive License Form | `/incentive-licenses/create`, `/incentive-licenses/:id/edit` | Company, License FK | HybridSelect |

### Report/Filter Pages
| Page | Path | Masters Used | Selector Type |
|---|---|---|---|
| Item Pivot Report | `/reports/item-pivot` | Company (include/exclude multi) | AsyncSelectField |
| Item Report | `/reports/items` | Company (include/exclude multi), SION | AsyncSelectField |
| License Purchase Profit | `/reports/license-purchase-profit` | Company (multi) | AsyncSelectField |
| License Ledger | `/ledger` | Company, SION, Purchase Status | AsyncSelectField |

### Modals/Inline Components
| Component | Usage | Masters Used | Selector Type |
|---|---|---|---|
| AllotmentFormModal | Inline edit of allotment | Company, Port, Exchange Rate | HybridSelect |
| LicenseBalanceModal | Show available items | Item Name (read-only) | AsyncSelect |
| TransferLetterForm | Modal for transfer letter selection | Company, Transfer Letter | AsyncSelectField |
| InlineNormEditor | Edit norm class on license card | SION | AsyncSelectField |
| LinkRecordModal | Reconciliation page | BOE/Invoice FK | HybridSelect |

### Background API Calls (Not Direct UI Selectors)
| Component | Master Fetched | Purpose |
|---|---|---|
| LedgerTab | Item Names | Fetch available items for search |
| useMasterFormCalculations | SION Classes | Validate unit price on export row save |
| ActivityLog | (all Master models) | Read-only activity audit log |
| ItemPivotReport | SION Classes (once on mount) | Populate norm class list for rendering |

---

## Loading States & Error Handling Matrix

### Component Behaviors

#### AsyncSelectField
| Scenario | State | Visual | User Feedback |
|---|---|---|---|
| **Mounting with value** | Fetching by ID | Spinner during lookup | Spinner only (no explicit message) |
| **Typing in search** | Debouncing → Fetching | Spinner (searchPending indicator) | "Searching…" in dropdown |
| **API Error on search** | Fallback to empty array | Menu closes, no error toast | Silent failure (no feedback) |
| **API Error on detail fetch** | Returns null, selection cleared | Menu displays empty | Silent failure |
| **No results** | After search complete | "No matches for X" message | ✅ Clear message |
| **Opening with no query** | Shows recent selections (if any) | Recent list appears | ✅ Helpful recent history |

#### HybridSelect
| Scenario | State | Visual | User Feedback |
|---|---|---|---|
| **Async endpoint mount** | Loads full first page (loadOnMount=true) | No explicit loading indicator | None (form-embedded, not obvious) |
| **FK deleted** | Fetches detail by ID, 404 returns null | Option hidden but selection may show stale label | ❌ No warning |
| **Typing to search** | Fetches with search param | No loading spinner visible | ❌ User unaware if slow |
| **API Error** | Empty array returned | No options appear | ❌ No error message |

#### DebouncedAsyncSelect
| Scenario | State | Visual | User Feedback |
|---|---|---|---|
| **Search pending** | Debouncing | Loading spinner appears | None (spinner self-explanatory) |
| **API Error** | Empty array | Menu closes | ❌ Silent failure |

#### usePurchaseStatusOptions (Hook)
| Scenario | State | Visual | User Feedback |
|---|---|---|---|
| **First mount** | Fetching from API | No spinner (hook doesn't expose it) | ❌ No loading state visible |
| **Cached hit** | Returns from module cache | Instant | ✅ Fast, seamless |
| **API Error** | Returns empty array, cache.data = [] | Multi-select shows no options | ❌ Silent, no recovery |

---

## Invalid Selection Handling

### Scenario: Deleted Master After Selection

**Current Behavior:**
1. User selects Company ID=5, form saves with `company: 5`
2. Admin deletes Company ID=5 from masters
3. User re-opens form
4. AsyncSelectField tries to fetch `/masters/companies/5/` → **404**
5. `fetchOptionById` catches error, returns `null`
6. `setSelectedOption(null)` → **field appears empty**
7. User must re-select a valid company

**Issues:**
- No warning that the previous selection is no longer valid
- Form silently clears the field
- If user saves without re-selecting, dependent data (BOE linked by company) breaks on backend

### Scenario: Stale Selection (Master edited but ID preserved)

**Current Behavior:**
1. User selects Company "ABC Inc" (ID=5), label cached
2. Admin renames it to "XYZ Inc" in masters
3. User re-opens form
4. Cached label still shows "ABC Inc" until component re-renders
5. User may submit form with stale label understanding

**Issues:**
- Label may not reflect current state
- No refresh button to manually sync

### Scenario: Sync Delay (MDS not yet propagated)

**Current Behavior:**
1. Frontend creates new Company "DEF Corp" (ID=99) via form
2. User tries to link it in Trade form immediately
3. If MDS is slow, Company ID=99 may not appear in search results
4. User cannot select it yet

**Mitigation:** Exists but implicit — backend Master API serves local ORM tables, MDS mirrors them asynchronously. Form save succeeds if the ID exists locally.

---

## Caching Strategy Analysis

### Session-Scoped Caching (Good)

#### useMasterOptions Hook — Module Cache
```javascript
const purchaseStatusCache: OptionsCache = { promise: null, data: null };
```
- **Scope:** Module-level (shared across all components in same session)
- **Lifetime:** Session duration
- **TTL:** None (no expiration)
- **Hit Rate:** High for heavily-used filters (Purchase Status, SION Norms)
- **Invalidation:** None (manual refresh required for hot updates)

#### AsyncSelectField — Recent Selections (sessionStorage)
```javascript
const recentsKey = `${RECENTS_STORAGE_PREFIX}${baseEndpoint}`;
```
- **Scope:** Per-endpoint in sessionStorage
- **Lifetime:** Session duration (cleared on tab close)
- **Capacity:** Last 5 selections per endpoint
- **Benefit:** Fast re-selection of recently-picked items

#### AsyncSelectField — FK Detail Cache
```javascript
const _fkDetailCache = new Map(); // in-memory
const _fkInFlight = new Map();    // in-flight coalescing
```
- **Scope:** In-memory per session
- **Lifetime:** Until page reload
- **Hit Rate:** Medium (tables with repeated FK columns)
- **Deduplication:** In-flight requests coalesced (prevents N+1 on multi-row forms)

### Gaps in Caching

⚠️ **No TTL or invalidation strategy:**
- If a Master is updated by another user, current session doesn't see it until refresh
- Long-running forms may display stale labels
- Appropriate for label display, but problematic if the Master data was critical (e.g., exchange rates, prices)

⚠️ **No "background refresh" on stale cache:**
- useMasterOptions doesn't refresh after X minutes
- SessionStorage recents persist even if Master was deleted

⚠️ **No explicit invalidation endpoint:**
- Admin changes Purchase Status order → all sessions still see old order
- No cache-busting signal from backend

---

## Pagination Analysis

### Current Pagination in Selectors

#### AsyncSelectField
```javascript
params.set('page_size', '50');  // Hard-coded limit
```

#### useMasterOptions
```javascript
params: { ..., page_size: 200 }  // For Purchase Status
params: { ..., page_size: 500 }  // For SION Norms
```

### Gap Identified ⚠️

**Problem:** If a Master has >50 items (or >200 for cached hooks), dropdown menu doesn't show "Load More" button.

**Affected Masters:**
- **SION Norm Classes:** ~2000+ total norms, but filtered by `is_active=true` (~handful). Safe.
- **Company:** Typically <50 in small orgs, but large enterprises may exceed 50. **Risky.**
- **HS Codes:** Large government catalogue (thousands). **Unsafe.**
- **Notification Numbers:** Small list, safe.

**User Experience:**
1. User types "Company A" in field
2. API returns top 50 matches
3. If "Company ABC Ltd" is match #51, **user cannot find it**
4. User thinks it doesn't exist

**Solutions Needed:**
- Increase page_size to 100-200 for large Masters
- Or add react-select's `onMenuScrollToBottom` to load next page
- Or implement virtual scrolling for large lists

---

## Search & Filter Behavior

### Search Implementation ✅

All selectors use `?search=` parameter on backend:
```javascript
params.set('search', inputValue);
api.get(`${baseEndpoint}?${params.toString()}`);
```

Backend filters by multiple fields (defined in DRF serializer searchable_fields).

### Debouncing ✅

**Delays:**
- AsyncSelectField: 300ms (configurable)
- DebouncedAsyncSelect: 300ms (configurable)
- HybridSelect: Inherits AsyncSelectField's 300ms

**Benefit:** Reduces API calls while typing.

### Duplicate Handling

**Scenario:** User types "Company A", selects Company ID=5, then types again and selects Company ID=5 again.

**Current:** Both selections appear in multi-select (no deduplication in UI).

**Backend Validation:** Depends on model constraints (if unique constraint exists, form submit fails).

---

## Accessibility & UX Improvements

### Current ✅
- ARIA labels on some fields (`aria-label` prop available)
- Keyboard navigation via react-select (Tab, Enter, Arrow keys)
- Recent selections shown on focus (helpful for power users)

### Gaps ⚠️
- No aria-live regions for loading/error states
- No explicit "no results" state in HybridSelect (silent empty)
- Spinner indicator not announced to screen readers

---

## Backend API Validation Issues

### What the Frontend Assumes About Master APIs

1. **All endpoints return paginated JSON** with `results` array:
   ```json
   { "results": [...], "count": 100, "next": "..." }
   ```
   Or direct array in some cases (handled as fallback).

2. **Search fields are always available:**
   ```
   GET /masters/companies/?search=ABC
   ```
   Backend must support `search` parameter.

3. **is_active filtering exists on some Masters:**
   ```
   GET /masters/sion-classes/?is_active=true
   ```
   SION Norms and Purchase Statuses explicitly filter by `is_active`.

4. **Ordering is consistent:**
   ```
   GET /masters/purchase-statuses/?ordering=display_order,label
   ```
   Frontend trusts backend's `display_order` field.

### Gaps in Backend Assumption Validation ⚠️

- Frontend doesn't check if endpoint exists (relies on HTTP 404)
- Frontend doesn't validate response schema (assumes `results` or bare array)
- Frontend doesn't handle redirect responses (if API moved)

---

## Test Coverage Analysis

### Unit Test Files Found ✅
- `MasterForm.smoke.test.tsx` — Smoke tests for Master CRUD form
- `MasterList.smoke.test.tsx` — Smoke tests for Master list page
- `AsyncSelectField` — No dedicated test file (used in integration tests only)
- `useMasterOptions.ts` — No test file

### Gaps in Test Coverage ⚠️

**AsyncSelectField:**
- No test for deleted FK recovery
- No test for pagination edge cases (51+ items)
- No test for recent selections persistence
- No test for concurrent request deduplication
- No test for cache invalidation on value change

**HybridSelect:**
- No test for endpoint switching (FK vs. direct)
- No test for custom label formatting

**useMasterOptions:**
- No test for module cache behavior
- No test for concurrent requests in multiple tabs

**Error Scenarios:**
- No test for network timeout
- No test for malformed API response
- No test for deleted Master selection recovery

---

## Recommendations

### High Priority 🔴

1. **Add "Master deleted" recovery UI:**
   - Show warning badge if selected Master 404s
   - Offer one-click "re-select" button
   - Save stale selection to localStorage backup

2. **Increase pagination limits:**
   - Company: page_size=100 (currently 50)
   - HS Codes: page_size=200 (currently 50)
   - Or implement virtual scrolling in react-select

3. **Add error toast feedback:**
   - Network errors on search show toast notification
   - Failed FK detail fetch shows tooltip

### Medium Priority 🟡

4. **Add TTL to module-scoped caches:**
   - useMasterOptions cache expires after 10 minutes
   - Option to manually refresh via button on filter panel

5. **Add refresh indicator on HybridSelect:**
   - Show spinner during async load on mount
   - Label "Loading options..." during fetch

6. **Implement virtual scrolling:**
   - For Masters with >500 items
   - Improves performance on slow networks

7. **Add cache invalidation endpoint:**
   - POST /api/cache/invalidate/ to clear session caches
   - Called by Master edit/delete operations if needed

### Low Priority 🟢

8. **Improve accessibility:**
   - Add aria-live regions for loading states
   - Announce "no results" and search spinner to screen readers
   - Test with keyboard-only navigation

9. **Add stale data warning:**
   - Warn if cache was last refreshed >10 min ago
   - Option to refresh on demand

10. **Deduplicate multi-select values:**
    - Frontend deduplication in HybridSelect onChange
    - Prevent user from selecting same Master twice

---

## Compliance Checklist

| Requirement | Status | Notes |
|---|---|---|
| All Master endpoints configured in backend | ✅ | 14/14 Masters in urls.py |
| Frontend selectors route to correct API | ✅ | endpoint parameter matches Django router |
| Loading states visible | ⚠️ | AsyncSelectField has spinner, HybridSelect lacks visible indicator |
| Empty states handled | ✅ | "No matches for X" message shown |
| Error states graceful | ⚠️ | Silent failures in some components, no recovery |
| Retry logic present | ❌ | No automatic retry on transient failures |
| Stale state handling | ⚠️ | Relies on API 404 fallback, no explicit warning |
| Duplicate options prevention | ❌ | UI allows duplicate selections in multi-select |
| Pagination visible | ❌ | No "load more" indicator in dropdowns |
| Search functionality | ✅ | Debounced API search working |
| Caching strategy | ✅ | Module-level + FK detail cache |
| Invalid selection recovery | ⚠️ | Manual re-select required after Master deletion |
| Deleted Master handling | ⚠️ | Field clears silently, no user notification |
| Sync delay handling | ✅ | Backend serves local ORM; MDS is eventual consistency |

---

## Conclusion

The frontend Master selector architecture is **well-designed and generally robust**. The use of AsyncSelectField as a shared component with debouncing, caching, and recent selections provides a solid UX foundation. All 14 backend Master APIs are correctly integrated with proper field mappings and type handling.

**Main gaps** are in error messaging (silent failures), deleted Master recovery (no warning), and pagination visibility (no load-more button). These are **moderate UX issues** rather than data-integrity risks, since the backend still enforces constraints.

**Recommended next steps:**
1. Add error toast notifications for network failures
2. Implement "Master deleted" warning with recovery UI
3. Increase pagination limits and add load-more button
4. Add TTL to module-scoped caches (useMasterOptions)
5. Test error scenarios with integration tests

---

## Appendix: Master API Endpoint Reference

```bash
GET /api/masters/companies/                    # Company master
GET /api/masters/ports/                        # Port master
GET /api/masters/hs-codes/                     # HS Code master
GET /api/masters/head-norms/                   # Head SION Norms master
GET /api/masters/sion-classes/                 # SION Norm Class master
GET /api/masters/product-descriptions/         # Product Description master
GET /api/masters/unit-prices/                  # Unit Price master
GET /api/masters/item-names/                   # Item Name master
GET /api/masters/groups/                       # Group master
GET /api/masters/exchange-rates/               # Exchange Rate master
GET /api/masters/transfer-letters/             # Transfer Letter master
GET /api/masters/purchase-statuses/            # Purchase Status master
GET /api/masters/scheme-codes/                 # Scheme Code master
GET /api/masters/notification-numbers/         # Notification Number master
```

**Common query parameters:**
- `search=<text>` — Text search across searchable fields
- `is_active=true` — Filter active records (available on status masters)
- `ordering=<field>` — Sort by field (e.g., `ordering=display_order,label`)
- `page_size=<n>` — Results per page (default varies, typically 20)
- `page=<n>` — Page number for pagination

