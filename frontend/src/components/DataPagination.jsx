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
        <div className="d-flex justify-content-between align-items-center mt-3">
            {/* Page Size Selector */}
            <div className="d-flex align-items-center">
                <label className="me-2 mb-0">Show:</label>
                <select
                    className="form-select form-select-sm"
                    style={{width: "auto"}}
                    value={pageSize}
                    onChange={handlePageSizeChange}
                >
                    {pageSizeOptions.map(size => (
                        <option key={size} value={size}>{size}</option>
                    ))}
                </select>
                <span className="ms-2 text-muted">per page</span>
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
                        >
                            <i className="bi bi-chevron-left"></i>
                        </button>
                    </li>

                    {/* Page Numbers */}
                    {getPageNumbers().map((page, index) => {
                        if (page === "...") {
                            return (
                                <li key={`ellipsis-${index}`} className="page-item disabled">
                                    <span className="page-link">...</span>
                                </li>
                            );
                        }

                        return (
                            <li
                                key={page}
                                className={`page-item ${currentPage === page ? "active" : ""}`}
                            >
                                <button
                                    className="page-link"
                                    onClick={() => handlePageChange(page)}
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
                        >
                            <i className="bi bi-chevron-right"></i>
                        </button>
                    </li>
                </ul>
            </nav>

            {/* Page Info */}
            <div className="text-muted">
                Page {currentPage} of {totalPages}
            </div>
        </div>
    );
}
