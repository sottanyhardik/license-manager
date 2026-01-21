/**
 * Reusable DataPagination Component
 *
 * Props:
 * - currentPage: current page number
 * - totalPages: total number of pages
 * - pageSize: items per page
 * - hasNext: boolean
 * - hasPrevious: boolean
 * - onPageChange: callback function(page)
 * - onPageSizeChange: callback function(pageSize)
 */
export default function DataPagination({
    currentPage = 1,
    totalPages = 1,
    pageSize = 25,
    hasNext = false,
    hasPrevious = false,
    onPageChange,
    onPageSizeChange
}) {
    const pageSizeOptions = [10, 25, 50, 100, 200];

    const handlePageChange = (page) => {
        if (page >= 1 && page <= totalPages) {
            onPageChange(page);
        }
    };

    const handlePageSizeChange = (e) => {
        const newSize = parseInt(e.target.value);
        onPageSizeChange(newSize);
    };

    // Generate page numbers to show
    const getPageNumbers = () => {
        const pages = [];
        const maxVisible = 5;

        if (totalPages <= maxVisible) {
            // Show all pages
            for (let i = 1; i <= totalPages; i++) {
                pages.push(i);
            }
        } else {
            // Show current page with 2 pages on each side
            let start = Math.max(1, currentPage - 2);
            let end = Math.min(totalPages, currentPage + 2);

            // Adjust if we're near the beginning or end
            if (currentPage <= 3) {
                end = maxVisible;
            } else if (currentPage >= totalPages - 2) {
                start = totalPages - maxVisible + 1;
            }

            // Add first page and ellipsis if needed
            if (start > 1) {
                pages.push(1);
                if (start > 2) pages.push("...");
            }

            // Add visible pages
            for (let i = start; i <= end; i++) {
                pages.push(i);
            }

            // Add ellipsis and last page if needed
            if (end < totalPages) {
                if (end < totalPages - 1) pages.push("...");
                pages.push(totalPages);
            }
        }

        return pages;
    };

    return (
        <div className="d-flex justify-content-between align-items-center mt-4 pt-3" style={{ borderTop: '1px solid #e5e7eb' }}>
            {/* Page Size Selector */}
            <div className="d-flex align-items-center">
                <label className="me-2 mb-0" style={{ fontSize: '0.9rem', fontWeight: '500', color: '#6b7280' }}>Show:</label>
                <select
                    className="form-select form-select-sm"
                    style={{
                        width: "auto",
                        borderRadius: '8px',
                        border: '1px solid #d1d5db',
                        padding: '6px 12px',
                        fontWeight: '500'
                    }}
                    value={pageSize}
                    onChange={handlePageSizeChange}
                >
                    {pageSizeOptions.map(size => (
                        <option key={size} value={size}>{size}</option>
                    ))}
                </select>
                <span className="ms-2" style={{ fontSize: '0.9rem', color: '#6b7280' }}>per page</span>
            </div>

            {/* Pagination Controls */}
            <nav>
                <ul className="pagination mb-0">
                    {/* Previous Button */}
                    <li className={`page-item ${!hasPrevious ? "disabled" : ""}`}>
                        <button
                            className="page-link"
                            onClick={() => handlePageChange(currentPage - 1)}
                            disabled={!hasPrevious}
                            style={{
                                borderRadius: '8px 0 0 8px',
                                fontWeight: '500',
                                padding: '8px 12px',
                                border: '1px solid #d1d5db'
                            }}
                        >
                            <i className="bi bi-chevron-left"></i>
                        </button>
                    </li>

                    {/* Page Numbers */}
                    {getPageNumbers().map((page, index) => {
                        if (page === "...") {
                            return (
                                <li key={`ellipsis-${index}`} className="page-item disabled">
                                    <span className="page-link" style={{ border: '1px solid #d1d5db', padding: '8px 12px' }}>...</span>
                                </li>
                            );
                        }

                        const isActive = currentPage === page;
                        return (
                            <li
                                key={page}
                                className={`page-item ${isActive ? "active" : ""}`}
                            >
                                <button
                                    className="page-link"
                                    onClick={() => handlePageChange(page)}
                                    style={{
                                        fontWeight: '500',
                                        padding: '8px 12px',
                                        border: '1px solid #d1d5db',
                                        ...(isActive && {
                                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                            borderColor: '#667eea',
                                            color: 'white'
                                        })
                                    }}
                                >
                                    {page}
                                </button>
                            </li>
                        );
                    })}

                    {/* Next Button */}
                    <li className={`page-item ${!hasNext ? "disabled" : ""}`}>
                        <button
                            className="page-link"
                            onClick={() => handlePageChange(currentPage + 1)}
                            disabled={!hasNext}
                            style={{
                                borderRadius: '0 8px 8px 0',
                                fontWeight: '500',
                                padding: '8px 12px',
                                border: '1px solid #d1d5db'
                            }}
                        >
                            <i className="bi bi-chevron-right"></i>
                        </button>
                    </li>
                </ul>
            </nav>

            {/* Page Info */}
            <div style={{ fontSize: '0.9rem', fontWeight: '500', color: '#6b7280' }}>
                Page {currentPage} of {totalPages}
            </div>
        </div>
    );
}
