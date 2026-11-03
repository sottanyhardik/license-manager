import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { LicenseFilterChip } from "../licenseListFilters";

interface ActiveFilterChipsProps {
  chips: LicenseFilterChip[];
  onRemove: (chip: LicenseFilterChip) => void;
  onClearAll: () => void;
}

/** One chip per active value. Each × removes only that value. Clear all returns to the baseline. */
export function ActiveFilterChips({ chips, onRemove, onClearAll }: ActiveFilterChipsProps) {
  if (chips.length === 0) return null;
  return (
    <div role="group" aria-label="Active filters" className="flex flex-wrap items-center gap-2">
      {chips.map((chip) => (
        <span
          key={chip.key}
          data-testid="licence-filter-chip"
          className="inline-flex h-8 max-w-full items-center gap-1 rounded-full border border-border bg-muted py-0 pr-1 pl-3 text-xs font-medium text-foreground"
        >
          <span className="truncate">{chip.label}</span>
          <button
            type="button"
            aria-label={`Remove ${chip.label}`}
            onClick={() => onRemove(chip)}
            className="inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted-foreground outline-none hover:bg-background hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40"
          >
            <X className="size-3.5" aria-hidden="true" />
          </button>
        </span>
      ))}
      <Button type="button" variant="ghost" data-testid="licence-filters-clear" onClick={onClearAll}>
        Clear all
      </Button>
    </div>
  );
}
