# Frontend — Claude Context

> **Read this at the start of any frontend development session.**

---

## Stack

React 19 + TypeScript + Vite 6 + Tailwind v4 (CSS-first, no `tailwind.config.ts`) + shadcn/ui + TanStack Query v5 + axios.

---

## Critical Configuration

### Tailwind v4 CSS-first

```css
/* src/app/globals.css */
@import "tailwindcss";
@theme inline {
  --color-primary: hsl(var(--primary));
  --color-background: hsl(var(--background));
  /* ... all shadcn CSS vars mapped to --color-* namespace */
}
```

**Without the `@theme inline` block, `bg-primary` renders nothing.** This was the bug that made buttons invisible.

### Vite Proxy

```typescript
// vite.config.ts
proxy: {
  '/api/v1': { target: 'http://localhost:8001' },  // NEW BACKEND — must be BEFORE /api/
  '/api':    { target: 'http://localhost:8000' },  // LEGACY BACKEND
}
```

Order matters — `/api/v1` must come before `/api`.

### API_HOST

```typescript
// client.ts
export const API_HOST = (
  import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? ''
).replace(/\/+$/, '')
```

In Docker: set `VITE_API_BASE_URL=http://api:8001`. Without it, Vite proxy handles routing.

---

## AuthContext: What to Know

**RBAC check pattern** — superuser sees ALL nav items:
```typescript
// hasAnyRole in AuthContext
if (user?.is_superuser) return true   // requires is_superuser in API response
```

`is_superuser` must be in the `/api/v1/auth/login/` and `/api/v1/auth/me/` responses. It's now in `UserSerializer` (fixed 2026-07-15). If it disappears from the serializer, ALL role-gated navigation items will be hidden for superusers.

**Token storage**: `localStorage`. XSS risk accepted (no HttpOnly cookie architecture).

**Proactive refresh**: uses `axios.post(${API_HOST}${ENDPOINTS.AUTH.REFRESH})` — NOT apiClient. This is intentional: using apiClient would risk recursive interceptor calls.

---

## Response Envelope Unwrap

The axios interceptor in `client.ts` automatically unwraps the backend envelope:
- `{success: true, data: {...}}` → response.data becomes `{...}`
- `{success: true, data: [...], pagination: {...}}` → response.data becomes `{data: [...], pagination: {...}}`
- `{success: false, errors: [...]}` → Promise.reject
- Blob responses (`responseType: 'blob'`): **bypass unwrap entirely** (early return guard added)

---

## Sidebar RBAC Gate

```typescript
// Sidebar.tsx: SidebarLink component
if (item.roles && !hasAnyRole(item.roles)) return null
```

Items with no `roles` property are always visible. Items with `roles` array are hidden when the user doesn't have any of those roles AND is not a superuser.

**Mobile behavior**: Sidebar is a fixed-position drawer on `< md` breakpoints. Opens via hamburger in TopBar (`md:hidden`). Closes on route change, Escape key, or backdrop click. State is lifted to `AdminLayout`.

---

## Query Key Convention

```typescript
['licenses']              // list
['licenses', id]          // detail  
['allotments']
['boe']
['boe', id]
['trades']
['tasks']
['dashboard', 'stats']
['dashboard', 'expiring']
['dashboard', 'utilisation']
['dashboard', 'activity']
['masters', 'companies']
['masters', 'ports']
['masters', 'hs-codes']
// etc.
```

**After any write mutation**: invalidate both list AND detail keys:
```typescript
queryClient.invalidateQueries({ queryKey: ['licenses'] })         // list
queryClient.invalidateQueries({ queryKey: ['licenses', id] })     // detail
```

After delete: use `removeQueries` for detail:
```typescript
queryClient.removeQueries({ queryKey: ['licenses', id] })
```

---

## PDF Download Pattern

**Never use `window.open(url)`** for authenticated PDF endpoints — no Authorization header is sent.

**Correct pattern**:
```typescript
const response = await apiClient.get(ENDPOINTS.TRADES.PURCHASE_INVOICE_PDF(id), {
  responseType: 'blob',
})
const url = URL.createObjectURL(response.data as Blob)
const a = document.createElement('a')
a.href = url; a.download = `file-${id}.pdf`
document.body.appendChild(a); a.click()
document.body.removeChild(a)
URL.revokeObjectURL(url)   // prevent memory leak
```

The `responseType: 'blob'` triggers the early-return guard in the envelope interceptor.

---

## Error Display Pattern (Login)

```typescript
// Client-side validation:
if (!username.trim()) { setError('Username is required.'); return }

// Server-side error:
} catch (err) {
  const msg = normaliseApiErrorString(err)
  setError(msg)       // inline banner
  toast.error(msg)    // also toast
}
```

Inline error clears on next keystroke via `onChange={(e) => { setValue(e.target.value); if (error) setError(null) }}`.

---

## Import Items Table Columns

Current columns (as of 2026-07-15):
```
Sr No | HS Code | Description | Total Qty | Planned | Allotted | Debited | Available | CIF FC | Balance CIF FC
```

"Planned" column shows `planned_quantity` from `LicenseItemPlan` (blue text). Shows `—` when no plan.

---

## Common Mistakes to Avoid

1. ❌ `window.open(pdfUrl)` — no auth header, returns 401
2. ❌ Only invalidating list key in mutation `onSuccess` — detail view stays stale
3. ❌ Missing blob guard in envelope interceptor — PDF binary treated as JSON
4. ❌ Using bare `axios` for proactive refresh without `API_HOST` prefix — 404 in Docker, user gets logged out
5. ❌ Removing `@theme inline` from globals.css — all `bg-primary` classes render nothing
6. ❌ Changing Vite proxy order (putting `/api/` before `/api/v1/`) — new backend endpoints unreachable
