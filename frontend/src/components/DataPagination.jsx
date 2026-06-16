export default function DataPagination({
    currentPage = 1,
    totalPages = 1,
    pageSize = 25,
    hasNext = false,
    hasPrevious = false,
    onPageChange,
    onPageSizeChange,
}) {
    const pageSizeOptions = [10, 25, 50, 100, 200];

    const handlePageChange = (page) => {
        if (page >= 1 && page <= totalPages) onPageChange(page);
    };

    const getPageNumbers = () => {
        const pages = [];
        const maxVisible = 5;
        if (totalPages <= maxVisible) {
            for (let i = 1; i <= totalPages; i++) pages.push(i);
        } else {
            let start = Math.max(1, currentPage - 2);
            let end = Math.min(totalPages, currentPage + 2);
            if (currentPage <= 3) end = maxVisible;
            else if (currentPage >= totalPages - 2) start = totalPages - maxVisible + 1;
            if (start > 1) { pages.push(1); if (start > 2) pages.push("..."); }
            for (let i = start; i <= end; i++) pages.push(i);
            if (end < totalPages) { if (end < totalPages - 1) pages.push("..."); pages.push(totalPages); }
        }
        return pages;
    };

    return (
        <div
            style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 12,
                marginTop: 16,
                paddingTop: 14,
                borderTop: "1px solid var(--tb-border-soft)",
            }}
        >
            {/* Page size selector */}
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <label htmlFor="page-size-select" style={{ fontSize: 12.5, fontWeight: 500, color: "var(--tb-text-secondary)", margin: 0 }}>
                    Show
                </label>
                <select
                    id="page-size-select"
                    className="form-select form-select-sm"
                    style={{ width: "auto" }}
                    value={pageSize}
                    onChange={e => onPageSizeChange(parseInt(e.target.value))}
                >
                    {pageSizeOptions.map(size => <option key={size} value={size}>{size}</option>)}
                </select>
                <span style={{ fontSize: 12.5, color: "var(--tb-text-secondary)" }}>per page</span>
            </div>

            {/* Page number buttons */}
            <nav aria-label="Pagination">
                <ul className="pagination mb-0" style={{ gap: 2 }}>
                    <li className={`page-item ${!hasPrevious ? "disabled" : ""}`}>
                        <button className="page-link" onClick={() => handlePageChange(currentPage - 1)} disabled={!hasPrevious} aria-label="Previous page" style={{ borderRadius: "var(--tb-r-sm)" }}>
                            <i className="bi bi-chevron-left" aria-hidden="true" />
                        </button>
                    </li>
                    {getPageNumbers().map((page, idx) => {
                        if (page === "...") {
                            return <li key={`e${idx}`} className="page-item disabled"><span className="page-link">…</span></li>;
                        }
                        const isActive = currentPage === page;
                        return (
                            <li key={page} className={`page-item ${isActive ? "active" : ""}`}>
                                <button className="page-link" onClick={() => handlePageChange(page)} aria-label={`Page ${page}`} aria-current={isActive ? "page" : undefined} style={{ borderRadius: "var(--tb-r-sm)", minWidth: 34 }}>
                                    {page}
                                </button>
                            </li>
                        );
                    })}
                    <li className={`page-item ${!hasNext ? "disabled" : ""}`}>
                        <button className="page-link" onClick={() => handlePageChange(currentPage + 1)} disabled={!hasNext} aria-label="Next page" style={{ borderRadius: "var(--tb-r-sm)" }}>
                            <i className="bi bi-chevron-right" aria-hidden="true" />
                        </button>
                    </li>
                </ul>
            </nav>

            <div style={{ fontSize: 12.5, color: "var(--tb-text-tertiary)", whiteSpace: "nowrap" }}>
                Page {currentPage} of {totalPages}
            </div>
        </div>
    );
}
