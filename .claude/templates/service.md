# Template — Frontend Service / API Module

Where: `frontend/src/services/` (domain functions) or `frontend/src/api/` (resource modules).
Always go through the shared axios instance — never `fetch()` or a second instance.
Rules: `.claude/rules/typescript.md`, `.claude/context/api.md`.

```ts
import api from "@/api/axios";
import type { Allotment, Paginated } from "@/types";

const BASE = "/api/allotments/";

export function listAllotments(params?: Record<string, unknown>) {
  return api.get<Paginated<Allotment>>(BASE, { params }).then((r) => r.data);
}

export function getAllotment(id: number) {
  return api.get<Allotment>(`${BASE}${id}/`).then((r) => r.data);
}

export function createAllotment(payload: Partial<Allotment>) {
  return api.post<Allotment>(BASE, payload).then((r) => r.data);
}

// Inline single-field edit (MasterViewSet supports PATCH on one field).
export function patchAllotmentField(id: number, field: keyof Allotment, value: unknown) {
  return api.patch<Allotment>(`${BASE}${id}/`, { [field]: value }).then((r) => r.data);
}
```

Notes: let the axios interceptors own 401/403/5xx; don't catch-and-swallow here. Reuse types
from `@/types`. Keep functions thin — no UI concerns in a service.
