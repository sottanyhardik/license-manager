# Frontend Architecture

> **Source of truth** — generated from actual implementation.  
> Last updated: 2026-07-15 (feature/V1).

---

## 1. Tech Stack

| Layer | Library | Version | Notes |
|---|---|---|---|
| UI framework | React | 19 | Concurrent rendering |
| Language | TypeScript | 5.x | Strict mode |
| Build tool | Vite | 6.x | CSS-first Tailwind v4 plugin |
| Styling | Tailwind CSS | 4.x | No tailwind.config.ts — CSS-first via `@import "tailwindcss"` |
| Component library | shadcn/ui | latest | Radix UI primitives + Tailwind |
| Server state | TanStack Query | v5 | `staleTime` tuned per entity |
| Routing | React Router | v6 | Declarative routes |
| HTTP client | axios | 1.x | JWT interceptors, envelope unwrap |
| Icons | lucide-react | latest | Consistent icon set |
| Notifications | sonner | latest | Toast notifications |
| Forms | React Hook Form + Zod | — | Validation |
| Charts | Recharts | — | Dashboard charts |

---

## 2. Directory Structure

```
frontend/src/
├── app/                    # App shell
│   ├── providers.tsx       # QueryClient + ThemeProvider + AuthProvider + Toaster
│   └── router.tsx          # All route definitions
├── features/               # Feature modules (one per business domain)
│   ├── allotments/
│   ├── bill-of-entry/
│   ├── dashboard/
│   ├── licenses/
│   ├── masters/
│   ├── reports/
│   ├── tasks/
│   └── trade/
├── layout/
│   └── AdminLayout.tsx     # Authenticated shell (sidebar + topbar + content)
├── pages/                  # Top-level pages (Login, NotFound, Settings)
│   ├── Login.tsx
│   ├── NotFound.tsx
│   └── settings/Settings.tsx
└── shared/                 # Cross-feature utilities
    ├── api/
    │   ├── client.ts       # axios instance, interceptors
    │   ├── endpoints.ts    # all API URL constants
    │   └── queryClient.ts  # TanStack Query global client
    ├── auth/
    │   ├── AuthContext.tsx # JWT state, token refresh, idle timeout
    │   ├── ProtectedRoute.tsx
    │   └── roles.ts        # 12 RBAC role constants + ROLE_GROUPS
    ├── hooks/
    │   ├── useDebounce.ts
    │   └── useLocalStorage.ts
    ├── routes.ts           # Route path constants (ROUTES object)
    ├── types/
    │   └── api.ts          # APIPaginatedData<T>, ListParams
    ├── ui/                 # Shared UI components
    │   ├── Sidebar.tsx
    │   ├── TopBar.tsx
    │   ├── ThemeProvider.tsx
    │   ├── badge.tsx button.tsx card.tsx input.tsx label.tsx skeleton.tsx
    │   └── index.ts
    └── utils/
        ├── cn.ts           # clsx + tailwind-merge
        ├── errors.ts       # normaliseApiErrorString
        └── formatters.ts   # number/date formatting
```

---

## 3. Route Definitions

All routes defined in `src/app/router.tsx`.

| Route | Component | Auth | Role Required |
|---|---|---|---|
| `/login` | `Login` | none | — |
| `/` → redirect | — | JWT | any |
| `/dashboard` | `Dashboard` | JWT | any |
| `/licenses` | `LicenseList` | JWT | LICENSE_ANY |
| `/licenses/:id` | `LicenseDetail` | JWT | LICENSE_ANY |
| `/allotments` | `AllotmentList` | JWT | ALLOTMENT_ANY |
| `/boe` | `BOEList` | JWT | BOE_ANY |
| `/boe/:id` | `BOEDetail` | JWT | BOE_ANY |
| `/trades` | `TradeList` | JWT | TRADE_ANY |
| `/trades/new` | `TradeForm` | JWT | TRADE_MANAGER |
| `/trades/:id` | `TradeForm` | JWT | TRADE_MANAGER |
| `/reports` | `ReportsIndex` | JWT | CAN_VIEW_REPORTS |
| `/reports/balance` | `BalanceReport` | JWT | CAN_VIEW_REPORTS |
| `/reports/items` | `ItemReport` | JWT | CAN_VIEW_REPORTS |
| `/reports/pivot` | `PivotReport` | JWT | CAN_VIEW_REPORTS |
| `/reports/ledger` | `LedgerReport` | JWT | CAN_VIEW_REPORTS |
| `/masters/:entity` | `MasterList` (generic) | JWT | any (write: superuser) |
| `/masters/companies` | `CompanyList` | JWT | any |
| `/masters/ports` | `PortList` | JWT | any |
| `/tasks` | `TaskList` | JWT | any |
| `/settings` | `Settings` | JWT | any |
| `*` | `NotFound` | none | — |

---

## 4. AuthContext

**File**: `src/shared/auth/AuthContext.tsx`

### State Shape
```typescript
interface AuthUser {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  is_superuser: boolean  // Added in fix: was missing from API, caused nav hide
  roles: Role[]
}
```

### What localStorage Stores

| Key | Value | Notes |
|---|---|---|
| `access` | JWT access token | 30-minute expiry |
| `refresh` | JWT refresh token | 7-day expiry |
| `user` | JSON-serialized `AuthUser` | Restored on page load |
| `sidebar-collapsed` | `"true"` / `"false"` | Sidebar preference |
| `theme` | `"dark"` / `"light"` | Theme preference |

### Context Functions

| Function | Description |
|---|---|
| `loginSuccess(data)` | Stores tokens + user, starts timers |
| `logout(reason?)` | Clears localStorage, redirects to /login |
| `hasRole(roleCode)` | True if superuser OR user has role |
| `hasAnyRole(roleCodes[])` | True if superuser OR has any of the roles |
| `isSuperAdmin()` | True if `user.is_superuser === true` |
| `canManageUsers()` | True if superuser OR has USER_MANAGER role |

### Timers

1. **Idle timeout**: Checks every 60s. If last activity > 30min ago → `logout('idle')`
2. **Proactive refresh**: Fires `TOKEN_REFRESH_BUFFER_MS` (5 min) before access token expiry → refreshes silently
   - Uses raw `axios.post(${API_HOST}${ENDPOINTS.AUTH.REFRESH})` — NOT apiClient (prevents circular interceptor issue)

---

## 5. API Client

**File**: `src/shared/api/client.ts`

### Base URL Resolution
```typescript
export const API_HOST = (
  import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? ''
).replace(/\/+$/, '')
```

Vite proxy in `vite.config.ts` routes:
- `/api/v1/*` → `http://localhost:8001` (new backend)
- `/api/*` → `http://localhost:8000` (legacy)

### Request Interceptor
Attaches `Authorization: Bearer {access}` from localStorage on every request.

### Response Interceptor — Envelope Unwrap
```typescript
// Blob responses: pass through unchanged (PDF downloads)
if (response.config.responseType === 'blob') return response

// Success response: unwrap data from envelope
if (envelope.success === true) {
  if ('pagination' in envelope) {
    response.data = { data: envelope.data, pagination: envelope.pagination }
  } else {
    response.data = envelope.data
  }
}

// Error response: reject with structured error
if (!envelope.success) {
  return Promise.reject({ message: envelope.message, errors: envelope.errors })
}
```

### 401 Refresh Queue
If a 401 is received and a refresh is not already in progress:
1. Set `isRefreshing = true`
2. Queue the failed request in `failedQueue`
3. Attempt refresh via `axios.post(${API_HOST}${ENDPOINTS.AUTH.REFRESH})`
4. On success: update localStorage, `processQueue(null, newToken)` → retry all queued requests
5. On failure: `processQueue(error)` → reject all queued, call `logout('session_expired')`

---

## 6. RBAC Role Constants

**File**: `src/shared/auth/roles.ts`

```typescript
const ROLES = {
  LICENSE_MANAGER: 'LICENSE_MANAGER',
  LICENSE_VIEWER: 'LICENSE_VIEWER',
  ALLOTMENT_MANAGER: 'ALLOTMENT_MANAGER',
  ALLOTMENT_VIEWER: 'ALLOTMENT_VIEWER',
  BOE_MANAGER: 'BOE_MANAGER',
  BOE_VIEWER: 'BOE_VIEWER',
  TRADE_MANAGER: 'TRADE_MANAGER',
  TRADE_VIEWER: 'TRADE_VIEWER',
  INCENTIVE_LICENSE_MANAGER: 'INCENTIVE_LICENSE_MANAGER',
  INCENTIVE_LICENSE_VIEWER: 'INCENTIVE_LICENSE_VIEWER',
  REPORT_VIEWER: 'REPORT_VIEWER',
  USER_MANAGER: 'USER_MANAGER',
  ACCOUNT_ACCESS: 'ACCOUNT_ACCESS',
  LEDGER_MANAGER: 'LEDGER_MANAGER',
  TL_GENERATE: 'TL_GENERATE',
}
```

**ROLE_GROUPS** (pre-computed arrays for `hasAnyRole`):
- `LICENSE_ANY = [LICENSE_MANAGER, LICENSE_VIEWER]`
- `ALLOTMENT_ANY`, `BOE_ANY`, `TRADE_ANY`, etc.
- `CAN_VIEW_REPORTS = [REPORT_VIEWER, LICENSE_MANAGER, ...]`

---

## 7. TanStack Query Strategy

**Client config** (`src/shared/api/queryClient.ts`):
- Default `staleTime`: varies per entity (balance data: shorter; master data: longer)
- Default `gcTime`: 5 minutes

**Query key patterns**:
```typescript
['licenses']              → list
['licenses', id]          → detail
['licenses', id, 'balance'] → balance panel
['allotments']
['boe']
['trades']
['tasks']
['dashboard', 'stats']
['masters', 'companies']
// etc.
```

**Mutation invalidation**: After mutations, `queryClient.invalidateQueries({ queryKey: ['licenses'] })` and `queryClient.invalidateQueries({ queryKey: ['licenses', id] })` to refresh both list and detail.

---

## 8. Sidebar & Layout

**AdminLayout** (`src/layout/AdminLayout.tsx`):
- Lifts `mobileOpen: boolean` state
- Route change → `setMobileOpen(false)` via `useEffect`
- Escape key → `setMobileOpen(false)` via `useEffect`
- Mobile backdrop: `fixed inset-0 z-20 bg-black/50 md:hidden`
- Sidebar wrapper: `fixed inset-y-0 left-0 z-30 md:static` with `translate-x` transition

**Sidebar** (`src/shared/ui/Sidebar.tsx`):
- Collapsed state persisted in `localStorage` (desktop preference)
- `forceExpanded = true` when mobile drawer is open (always shows labels)
- `onLinkClick` prop closes mobile drawer after navigation
- Role-gated items use `hasAnyRole(item.roles)` — superusers see all items (requires `is_superuser: true` in API response)

**TopBar** (`src/shared/ui/TopBar.tsx`):
- Hamburger button: `md:hidden`, `aria-expanded`, `aria-controls="main-nav"`
- Breadcrumb: auto-generated from current pathname
- Theme toggle: light/dark
- User menu: display name, initials, profile link, logout

---

## 9. Login Page

**File**: `src/pages/Login.tsx`

Design:
- Gradient background: `from-slate-50 to-slate-100`
- "LM" brand monogram above card
- `noValidate` on form (custom validation instead of browser native)
- Inline `role="alert"` error banner (clears on next keystroke)
- Show/hide password toggle (Eye/EyeOff icons, keyboard accessible)
- Spinner + "Signing in…" on submit
- `autoFocus` on username field

Error handling:
1. Client-side: empty username/password → inline banner
2. Server-side: invalid credentials → inline banner + toast
