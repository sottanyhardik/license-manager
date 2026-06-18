# Rule — React (v19)

Scope: `frontend/src/**`. See also `.claude/rules/typescript.md`, `.claude/rules/frontend-ui.md`,
and the canonical stack note in `.claude/rules.md`.

## Must

- **Function components only.** No class components.
- **Hooks at top level**, never conditional. Follow `eslint-plugin-react-hooks`.
- **Lazy-load pages** via the existing retry wrapper (`lazyLoadWithRetry`) — don't add raw
  `React.lazy` without the retry behavior. New routes go through `ProtectedRoute`.
- **Shared state** comes from existing contexts only: `AuthContext`, `ThemeContext`,
  `ToastContext`. Do **not** introduce Redux/Zustand/Context for page-local state.
- **Data fetching** goes through the axios instance (`@/api/axios`) or a `services/` module —
  never `fetch()` directly, never a second axios instance.
- **Keys** on lists must be stable IDs, not array indices.
- Co-locate a component with its page unless it's reused; reusable primitives live in
  `@/components/ui/`.

## Avoid

- `useEffect` for derived state (compute during render or `useMemo`).
- Prop drilling more than ~2 levels — lift to a context only if already shared.
- Premature `memo`/`useCallback`/`useMemo` — add only when a profile shows a real cost.
- Duplicate components — grep `components/` first.

## Pattern

```tsx
import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import api from "@/api/axios";

export function ThingActions({ thingId }: { thingId: number }) {
  const [saving, setSaving] = useState(false);
  const onSave = useCallback(async () => {
    setSaving(true);
    try {
      await api.patch(`/api/things/${thingId}/`, { … });
      toast.success("Saved");
    } finally {
      setSaving(false);
    }
  }, [thingId]);
  return <Button disabled={saving} onClick={onSave}>Save</Button>;
}
```

Template: `.claude/templates/component.md`.
