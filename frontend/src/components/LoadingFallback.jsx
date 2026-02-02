/**
 * LoadingFallback Component
 *
 * Provides various loading states for lazy-loaded components.
 * Uses skeleton screens and spinners for better UX.
 */

/**
 * Simple page-level loading spinner
 */
export function PageLoader() {
    return (
        <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
            <div className="text-center">
                <div className="spinner-border text-primary" role="status" style={{ width: '3rem', height: '3rem' }}>
                    <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-3 text-muted">Loading page...</p>
            </div>
        </div>
    );
}

/**
 * Full-screen loading overlay for route transitions
 */
export function FullPageLoader() {
    return (
        <div className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
             style={{
                 backgroundColor: 'rgba(255, 255, 255, 0.9)',
                 zIndex: 9999,
                 backdropFilter: 'blur(5px)'
             }}>
            <div className="text-center">
                <div className="spinner-grow text-primary mb-3" role="status" style={{ width: '4rem', height: '4rem' }}>
                    <span className="visually-hidden">Loading...</span>
                </div>
                <h5 className="text-primary">Loading...</h5>
                <p className="text-muted">Please wait</p>
            </div>
        </div>
    );
}

/**
 * Skeleton loader for table/list views
 */
export function TableSkeletonLoader({ rows = 5, columns = 5 }) {
    return (
        <div className="card">
            <div className="card-body">
                {/* Header skeleton */}
                <div className="d-flex justify-content-between mb-4">
                    <div className="placeholder-glow" style={{ width: '200px' }}>
                        <span className="placeholder col-12" style={{ height: '38px' }}></span>
                    </div>
                    <div className="placeholder-glow" style={{ width: '120px' }}>
                        <span className="placeholder col-12" style={{ height: '38px' }}></span>
                    </div>
                </div>

                {/* Table skeleton */}
                <div className="table-responsive">
                    <table className="table">
                        <thead>
                            <tr>
                                {Array.from({ length: columns }).map((_, i) => (
                                    <th key={i}>
                                        <div className="placeholder-glow">
                                            <span className="placeholder col-8"></span>
                                        </div>
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {Array.from({ length: rows }).map((_, rowIndex) => (
                                <tr key={rowIndex}>
                                    {Array.from({ length: columns }).map((_, colIndex) => (
                                        <td key={colIndex}>
                                            <div className="placeholder-glow">
                                                <span className="placeholder col-10"></span>
                                            </div>
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}

/**
 * Skeleton loader for form views
 */
export function FormSkeletonLoader({ fields = 6 }) {
    return (
        <div className="card">
            <div className="card-body">
                {/* Title skeleton */}
                <div className="placeholder-glow mb-4">
                    <span className="placeholder col-4" style={{ height: '32px' }}></span>
                </div>

                {/* Form fields skeleton */}
                <div className="row g-3">
                    {Array.from({ length: fields }).map((_, i) => (
                        <div key={i} className="col-md-6">
                            <div className="placeholder-glow mb-2">
                                <span className="placeholder col-4"></span>
                            </div>
                            <div className="placeholder-glow">
                                <span className="placeholder col-12" style={{ height: '38px' }}></span>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Button skeleton */}
                <div className="mt-4 placeholder-glow">
                    <span className="placeholder col-2" style={{ height: '38px' }}></span>
                </div>
            </div>
        </div>
    );
}

/**
 * Skeleton loader for dashboard/report views
 */
export function DashboardSkeletonLoader() {
    return (
        <div>
            {/* Stats cards skeleton */}
            <div className="row g-3 mb-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="col-md-3">
                        <div className="card">
                            <div className="card-body">
                                <div className="placeholder-glow mb-2">
                                    <span className="placeholder col-8"></span>
                                </div>
                                <div className="placeholder-glow">
                                    <span className="placeholder col-6" style={{ height: '40px' }}></span>
                                </div>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Chart/Table skeleton */}
            <div className="card">
                <div className="card-body">
                    <div className="placeholder-glow mb-3">
                        <span className="placeholder col-3"></span>
                    </div>
                    <div className="placeholder-glow">
                        <span className="placeholder col-12" style={{ height: '300px' }}></span>
                    </div>
                </div>
            </div>
        </div>
    );
}

/**
 * Minimal inline loader for small components
 */
export function InlineLoader({ text = "Loading..." }) {
    return (
        <div className="d-flex align-items-center gap-2 text-muted">
            <span className="spinner-border spinner-border-sm" role="status">
                <span className="visually-hidden">Loading...</span>
            </span>
            <span>{text}</span>
        </div>
    );
}

/**
 * Loading bar that appears at the top of the page
 */
export function LoadingBar() {
    return (
        <div className="position-fixed top-0 start-0 w-100" style={{ zIndex: 10000 }}>
            <div className="progress" style={{ height: '3px', borderRadius: 0 }}>
                <div
                    className="progress-bar progress-bar-striped progress-bar-animated bg-primary"
                    role="progressbar"
                    style={{ width: '100%' }}
                >
                </div>
            </div>
        </div>
    );
}

/**
 * Default export - simple page loader
 */
export default PageLoader;
