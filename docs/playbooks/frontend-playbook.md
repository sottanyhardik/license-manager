# Change Playbook: Frontend

> **Developer checklist for any frontend change.**

---

## Before Any Frontend Change

### Files to Read
```
1. docs/claude/frontend-context.md        ← patterns, pitfalls
2. docs/frontend/architecture.md          ← routes, auth, query keys
3. frontend/src/shared/api/client.ts      ← if touching API layer
4. frontend/src/shared/auth/AuthContext.tsx ← if touching auth
5. frontend/src/shared/ui/Sidebar.tsx     ← if touching navigation
6. frontend/src/layout/AdminLayout.tsx    ← if touching layout
```

### Critical Rules
1. **Never `window.open(url)`** for authenticated endpoints — use `apiClient.get({responseType:'blob'})`
2. **Always invalidate both list AND detail** query keys in mutation `onSuccess`
3. **`API_HOST` prefix** for all direct axios calls in AuthContext
4. **`@theme inline` block** in globals.css must never be removed
5. **Vite proxy order**: `/api/v1` before `/api/`
6. **`is_superuser`** in UserSerializer — never remove from backend

### Gate Before Committing
```bash
cd frontend
node_modules/.bin/tsc --noEmit   # Zero type errors
npm run build                     # Clean build
```

---

## Common Frontend Tasks

### Adding a New Feature Module

1. Create `frontend/src/features/{module}/`
2. Add files: `types.ts`, `queries.ts`, `mutations.ts`, `api.ts`, `index.ts`
3. Create `pages/` subdirectory with page components
4. Add route in `frontend/src/app/router.tsx`
5. Add sidebar item in `frontend/src/shared/ui/Sidebar.tsx` with `roles` array
6. Add ENDPOINTS in `frontend/src/shared/api/endpoints.ts`
7. Add route constant in `frontend/src/shared/routes.ts`
8. Update `docs/modules/{module}.md`

### Adding a New API Call

```typescript
// endpoints.ts
export const ENDPOINTS = {
  MY_MODULE: {
    LIST: '/api/v1/my-module/',
    DETAIL: (id: number) => `/api/v1/my-module/${id}/`,
    CUSTOM_ACTION: (id: number) => `/api/v1/my-module/${id}/action/`,
  }
}

// queries.ts
export function useMyModuleList(params?: ListParams) {
  return useQuery({
    queryKey: ['my-module', params],
    queryFn: async () => {
      const res = await apiClient.get<APIPaginatedData<MyType>>(
        ENDPOINTS.MY_MODULE.LIST, { params }
      )
      return res.data  // already unwrapped by interceptor
    },
  })
}

// mutations.ts
export function useCreateMyThing() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreatePayload) =>
      apiClient.post<MyType>(ENDPOINTS.MY_MODULE.LIST, data).then(r => r.data),
    onSuccess: (_data, _vars) => {
      queryClient.invalidateQueries({ queryKey: ['my-module'] })
    },
    onError: (err) => toast.error(normaliseApiErrorString(err)),
  })
}
```

### Adding a Navigation Item

```typescript
// Sidebar.tsx — add to TOP_NAV array
{
  label: 'My Module',
  path: ROUTES.MY_MODULE,
  icon: SomeIcon,
  roles: ROLE_GROUPS.MY_MODULE_ANY,  // or omit for all-users visibility
},
```

### Adding a Protected Route

```typescript
// router.tsx
<Route path={ROUTES.MY_MODULE} element={
  <ProtectedRoute allowedRoles={ROLE_GROUPS.MY_MODULE_ANY}>
    <MyModuleList />
  </ProtectedRoute>
} />
```

---

## After Changes

### Validation Checklist
- [ ] `node_modules/.bin/tsc --noEmit` — zero errors
- [ ] `npm run build` — clean build  
- [ ] Manual: login works
- [ ] Manual: navigation shows correct items for admin user
- [ ] Manual: test the changed feature
- [ ] Manual: test on mobile (375px) — sidebar drawer behavior

### Documentation Updates
- [ ] `docs/frontend/architecture.md` — routes section if routes changed
- [ ] `docs/modules/{module}.md` — frontend components section
- [ ] `docs/knowledge-graphs/dependency-maps.md` — if touching client.ts or globals.css
