import type { ReactNode } from "react";
import { Filter, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export function FilterPanel({ children, activeCount, isUpdating = false, onClear, clearDisabled = false }: {
  children: ReactNode; activeCount: number; isUpdating?: boolean; onClear: () => void; clearDisabled?: boolean;
}) {
  return <section aria-label="Filters" className="rounded-lg border border-border/70 bg-card shadow-sm">
    <div className="flex min-h-11 items-center gap-2 border-b border-border/60 px-3 py-2">
      <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
      <h2 className="text-sm font-semibold">Filters</h2>
      {activeCount > 0 && <span className="text-xs text-muted-foreground">{activeCount} active</span>}
      {isUpdating && <span role="status" className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="size-3 animate-spin motion-reduce:animate-none" />Updating</span>}
      <Button type="button" variant="ghost" size="sm" className={isUpdating ? "" : "ml-auto"} onClick={onClear} disabled={clearDisabled}><X className="size-3.5" />Clear Filters</Button>
    </div>
    <div className="p-3">{children}</div>
  </section>;
}

export function FilterGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

export function FilterField({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return <div className={wide ? "xl:col-span-2" : ""}>{children}</div>;
}
