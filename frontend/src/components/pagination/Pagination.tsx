import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { useId } from "react";
import { Button } from "@/components/ui/button";
import { PAGE_SIZES, PAGE_SIZE_MAX } from "@/lib/listContract";
import { cn } from "@/lib/utils";

export interface PaginationProps {
    page: number;
    totalPages: number;
    count: number;
    pageSize: number;
    hasPrevious: boolean;
    hasNext: boolean;
    onPageChange: (n: number) => void;
    onPageSizeChange?: (n: number) => void;
    /** Default [25, 50, 100, 200]. Sizes above 200 are dropped (server cap). */
    pageSizes?: readonly number[];
    className?: string;
}

/** Windowed page list: first, last, current +/- 1, with ellipses. */
function pageWindow(page: number, total: number): (number | "gap-l" | "gap-r")[] {
    const keep = new Set([1, total, page - 1, page, page + 1].filter((n) => n >= 1 && n <= total));
    const sorted = [...keep].sort((a, b) => a - b);
    const out: (number | "gap-l" | "gap-r")[] = [];
    sorted.forEach((n, i) => {
        if (i > 0 && n - sorted[i - 1] > 1) out.push(i === 1 ? "gap-l" : "gap-r");
        out.push(n);
    });
    return out;
}

export function Pagination({
    page, totalPages, count, pageSize, hasPrevious, hasNext,
    onPageChange, onPageSizeChange, pageSizes = PAGE_SIZES, className,
}: PaginationProps) {
    const selectId = useId();
    const sizes = [...new Set([...pageSizes.filter((s) => s <= PAGE_SIZE_MAX), ...(pageSize <= PAGE_SIZE_MAX ? [pageSize] : [])])].sort((a, b) => a - b);
    const total = Math.max(1, totalPages);
    const from = count === 0 ? 0 : (page - 1) * pageSize + 1;
    const to = Math.min(count, page * pageSize);
    const go = (n: number) => onPageChange(Math.min(Math.max(1, n), total));

    return (
        <nav aria-label="Pagination" className={cn("flex flex-wrap items-center justify-between gap-3 text-sm", className)}>
            <p aria-live="polite" className="text-xs text-muted-foreground tabular-nums">
                Rows {from}-{to} of {count}
            </p>
            <div className="flex flex-wrap items-center gap-3">
                {onPageSizeChange && (
                    <div className="flex items-center gap-2">
                        <label htmlFor={selectId} className="text-xs text-muted-foreground">Rows per page</label>
                        <select
                            id={selectId}
                            value={pageSize}
                            onChange={(e) => onPageSizeChange(Math.min(Number(e.target.value), PAGE_SIZE_MAX))}
                            className="h-8 rounded-md border border-input bg-card px-2 text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
                        >
                            {sizes.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                )}
                <div className="flex items-center gap-1">
                    <Button variant="outline" size="sm" aria-label="First page" disabled={!hasPrevious} onClick={() => go(1)}><ChevronsLeft /></Button>
                    <Button variant="outline" size="sm" aria-label="Previous page" disabled={!hasPrevious} onClick={() => go(page - 1)}><ChevronLeft /></Button>
                    {pageWindow(page, total).map((item) =>
                        typeof item === "string" ? (
                            <span key={item} aria-hidden="true" className="px-1 text-muted-foreground">…</span>
                        ) : (
                            <Button
                                key={item}
                                variant={item === page ? "default" : "outline"}
                                size="sm"
                                aria-label={`Page ${item}`}
                                aria-current={item === page ? "page" : undefined}
                                onClick={() => go(item)}
                                className="min-w-8 tabular-nums"
                            >
                                {item}
                            </Button>
                        ),
                    )}
                    <Button variant="outline" size="sm" aria-label="Next page" disabled={!hasNext} onClick={() => go(page + 1)}><ChevronRight /></Button>
                    <Button variant="outline" size="sm" aria-label="Last page" disabled={!hasNext} onClick={() => go(total)}><ChevronsRight /></Button>
                </div>
            </div>
        </nav>
    );
}
