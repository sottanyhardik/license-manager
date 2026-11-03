import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { EXPIRY_FILTERS, PAGE_SIZES, type ExpiryFilter, type PageSize } from "./listParams";

const EXPIRY_LABELS: Record<ExpiryFilter, string> = {
  all: "All",
  active: "Active",
  expired: "Expired",
};

const SEGMENT_BASE =
  "h-8 rounded-md px-3 text-sm font-medium outline-none transition-colors cursor-pointer focus-visible:ring-[3px] focus-visible:ring-ring/40";

interface ListToolbarProps {
  searchDraft: string;
  onSearchChange: (text: string) => void;
  expiry: ExpiryFilter;
  onExpiryChange: (expiry: ExpiryFilter) => void;
  pageSize: PageSize;
  onPageSizeChange: (pageSize: PageSize) => void;
}

export default function ListToolbar({
  searchDraft,
  onSearchChange,
  expiry,
  onExpiryChange,
  pageSize,
  onPageSizeChange,
}: ListToolbarProps) {
  return (
    <>
      <div className="relative min-w-[16rem] flex-1 sm:max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          type="search"
          value={searchDraft}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search licence or importer"
          aria-label="Search by licence number or importer"
          className="pl-9"
          autoComplete="off"
        />
      </div>

      <div role="group" aria-label="Filter by expiry" className="inline-flex rounded-lg border bg-card p-0.5">
        {EXPIRY_FILTERS.map((option) => {
          const pressed = option === expiry;
          return (
            <button
              key={option}
              type="button"
              aria-pressed={pressed}
              aria-label={`Expiry: ${EXPIRY_LABELS[option]}`}
              onClick={() => onExpiryChange(option)}
              className={cn(
                SEGMENT_BASE,
                pressed ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {EXPIRY_LABELS[option]}
            </button>
          );
        })}
      </div>

      <select
        aria-label="Rows per page"
        value={pageSize}
        onChange={(event) => onPageSizeChange(Number(event.target.value) as PageSize)}
        className="h-9 rounded-lg border border-input bg-card px-3 text-sm shadow-sm outline-none cursor-pointer focus-visible:ring-[3px] focus-visible:ring-ring/40"
      >
        {PAGE_SIZES.map((size) => (
          <option key={size} value={size}>
            {size} per page
          </option>
        ))}
      </select>
    </>
  );
}
