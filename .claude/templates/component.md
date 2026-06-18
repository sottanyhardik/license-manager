# Template — React Component (TS + shadcn/ui)

Rules: `.claude/rules/{react,typescript,frontend-ui}.md`. Reuse `@/components/ui/*` first.

```tsx
import { useState, useCallback } from "react";
import type { Thing } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import api from "@/api/axios";

interface ThingPanelProps {
  thing: Thing;
  className?: string;
  onUpdated?: (next: Thing) => void;
}

export function ThingPanel({ thing, className, onUpdated }: ThingPanelProps) {
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const { data } = await api.patch<Thing>(`/api/things/${thing.id}/`, { /* … */ });
      onUpdated?.(data);
      toast.success("Saved");
    } finally {
      setSaving(false);
    }
  }, [thing.id, onUpdated]);

  return (
    <Card className={cn("space-y-4", className)}>
      <CardHeader>
        <CardTitle>{thing.name}</CardTitle>
      </CardHeader>
      <CardContent>
        <Button disabled={saving} onClick={handleSave}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </CardContent>
    </Card>
  );
}
```

Checklist: typed props, `cn()` for class merge, `lucide-react` icons only, `sonner` for toasts,
data via `@/api/axios`, no new `.css`, AA-accessible, responsive.
