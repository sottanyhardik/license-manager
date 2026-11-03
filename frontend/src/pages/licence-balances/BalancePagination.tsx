import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatCount } from "./format";

interface BalancePaginationProps {
  /** Page actually served by the backend (may differ from the requested page). */
  page: number;
  pageSize: number;
  count: number;
  totalPages: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPageChange: (page: number) => void;
}

export default function BalancePagination({
  page,
  pageSize,
  count,
  totalPages,
  hasPrevious,
  hasNext,
  onPageChange,
}: BalancePaginationProps) {
  const first = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, count);

  return (
    <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-3 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 text-muted-foreground" aria-live="polite">
        <span>{`Showing ${formatCount(first)}–${formatCount(last)} of ${formatCount(count)}`}</span>
        {totalPages > 1 ? <span>{`Page ${formatCount(page)} of ${formatCount(totalPages)}`}</span> : null}
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          aria-label="Previous page"
          disabled={!hasPrevious}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" />
          Previous
        </Button>
        <Button variant="outline" size="sm" aria-label="Next page" disabled={!hasNext} onClick={() => onPageChange(page + 1)}>
          Next
          <ChevronRight aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
