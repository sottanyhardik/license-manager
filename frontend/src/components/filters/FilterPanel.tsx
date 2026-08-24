import { useEffect, useId, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, Filter, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export function FilterPanel({ children, activeCount, isUpdating = false, onClear, clearDisabled = false, collapsible = false, defaultOpen = true }: {
  children: ReactNode; activeCount: number; isUpdating?: boolean; onClear: () => void; clearDisabled?: boolean; collapsible?: boolean; defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const contentId = useId();

  // A filter selected outside the panel (for example from a saved URL) should
  // never be hidden from the person who needs to review it.
  useEffect(() => {
    if (activeCount > 0) setIsOpen(true);
  }, [activeCount]);

  return <section aria-label="Filters" className="overflow-hidden rounded-xl border border-border/70 bg-card shadow-sm">
    <div className="flex min-h-12 items-center gap-2 px-3 py-2 sm:px-4">
      <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
      <h2 className="text-sm font-semibold">Filters</h2>
      {activeCount > 0 && <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium tabular-nums text-primary">{activeCount} active</span>}
      {isUpdating && <span role="status" className="ml-auto hidden items-center gap-1 text-xs text-muted-foreground sm:inline-flex"><Loader2 className="size-3 animate-spin motion-reduce:animate-none" />Updating</span>}
      {!clearDisabled && <Button type="button" variant="ghost" size="sm" className={isUpdating ? "" : "ml-auto"} onClick={onClear}><X className="size-3.5" />Clear</Button>}
      {collapsible && <Button type="button" variant="ghost" size="sm" className={!clearDisabled || isUpdating ? "" : "ml-auto"} onClick={() => setIsOpen((open) => !open)} aria-expanded={isOpen} aria-controls={contentId}>
        {isOpen ? "Hide" : "Show"} {isOpen ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
      </Button>}
    </div>
    {isOpen && <div id={contentId} className="border-t border-border/60 p-3 sm:p-4">{children}</div>}
  </section>;
}

export function FilterGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

export function FilterField({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return <div className={wide ? "xl:col-span-2" : ""}>{children}</div>;
}
