import { ChevronLeft, ChevronRight } from "lucide-react";

export default function DataPagination({
    currentPage = 1,
    totalPages = 1,
    pageSize = 25,
    hasNext = false,
    hasPrevious = false,
    onPageChange,
    onPageSizeChange,
    totalItems,
}: {
    currentPage?: number;
    totalPages?: number;
    pageSize?: number;
    hasNext?: boolean;
    hasPrevious?: boolean;
    onPageChange: (page: number) => void;
    onPageSizeChange: (size: number) => void;
    totalItems?: number;
}) {
    const pageSizeOptions = [10, 25, 50, 100, 200];

    const handlePageChange = (page: number) => {
        if (page >= 1 && page <= totalPages) onPageChange(page);
    };

    const getPageNumbers = () => {
        const pages: (number | string)[] = [];
        const maxVisible = 5;
        if (totalPages <= maxVisible) {
            for (let i = 1; i <= totalPages; i++) pages.push(i);
        } else {
            let start = Math.max(1, currentPage - 2);
            let end = Math.min(totalPages, currentPage + 2);
            if (currentPage <= 3) end = maxVisible;
            else if (currentPage >= totalPages - 2) start = totalPages - maxVisible + 1;
            if (start > 1) { pages.push(1); if (start > 2) pages.push("…"); }
            for (let i = start; i <= end; i++) pages.push(i);
            if (end < totalPages) { if (end < totalPages - 1) pages.push("…"); pages.push(totalPages); }
        }
        return pages;
    };

    const startItem = totalItems ? (currentPage - 1) * pageSize + 1 : null;
    const endItem = totalItems ? Math.min(currentPage * pageSize, totalItems) : null;

    return (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 px-1 pt-3 mt-3">
            {/* Left: page size selector + count */}
            <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                    <span className="text-[12px] text-muted-foreground">Show</span>
                    <select
                        className="h-7 rounded-md border border-input bg-card px-2 text-[12px] outline-none focus-visible:border-ring cursor-pointer"
                        value={pageSize}
                        onChange={e => onPageSizeChange(parseInt(e.target.value))}
                        aria-label="Rows per page"
                    >
                        {pageSizeOptions.map(size => <option key={size} value={size}>{size}</option>)}
                    </select>
                    <span className="text-[12px] text-muted-foreground">per page</span>
                </div>
                {totalItems != null && (
                    <span className="hidden text-[12px] text-muted-foreground sm:inline-block">
                        {startItem}–{endItem} of {totalItems.toLocaleString()}
                    </span>
                )}
            </div>

            {/* Center: page number buttons */}
            <nav aria-label="Pagination" className="flex items-center gap-0.5">
                <button
                    onClick={() => handlePageChange(currentPage - 1)}
                    disabled={!hasPrevious}
                    aria-label="Previous page"
                    className="flex size-7 items-center justify-center rounded-md border border-border bg-card text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
                >
                    <ChevronLeft className="size-3.5" />
                </button>

                {getPageNumbers().map((page, idx) => {
                    if (page === "…") {
                        return (
                            <span key={`e${idx}`} className="flex size-7 items-center justify-center text-[12px] text-muted-foreground">
                                …
                            </span>
                        );
                    }
                    const isActive = currentPage === page;
                    return (
                        <button
                            key={page}
                            onClick={() => handlePageChange(page as number)}
                            aria-label={`Page ${page}`}
                            aria-current={isActive ? "page" : undefined}
                            className={`flex min-w-[28px] h-7 items-center justify-center rounded-md px-1.5 text-[12px] font-medium transition-colors ${
                                isActive
                                    ? "bg-primary text-primary-foreground shadow-sm"
                                    : "border border-border bg-card text-foreground hover:bg-muted"
                            }`}
                        >
                            {page}
                        </button>
                    );
                })}

                <button
                    onClick={() => handlePageChange(currentPage + 1)}
                    disabled={!hasNext}
                    aria-label="Next page"
                    className="flex size-7 items-center justify-center rounded-md border border-border bg-card text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
                >
                    <ChevronRight className="size-3.5" />
                </button>
            </nav>

            {/* Right: page indicator */}
            <span className="text-[12px] text-muted-foreground tabular-nums">
                {currentPage} / {totalPages}
            </span>
        </div>
    );
}
