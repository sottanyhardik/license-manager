import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../api/axios';

/**
 * PDF Viewer Component
 *
 * Opens PDFs in a dedicated route that can be refreshed to regenerate the PDF.
 * URL format: /pdf-viewer?url=/license-ledger/export/all/?params...
 */
export default function PDFViewer() {
    const [searchParams] = useSearchParams();
    const [pdfUrl, setPdfUrl] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const apiUrl = searchParams.get('url');

    useEffect(() => {
        let isMounted = true;
        let currentBlobUrl = null;

        const fetchPDF = async () => {
            if (!apiUrl) {
                if (isMounted) {
                    setError('No PDF URL provided');
                    setLoading(false);
                }
                return;
            }

            try {
                if (isMounted) {
                    setLoading(true);
                    setError(null);
                    setPdfUrl(null); // Clear previous PDF
                }

                const response = await api.get(apiUrl, {
                    responseType: 'blob'
                });

                if (!isMounted) return; // Don't update if unmounted

                const blob = new Blob([response.data], { type: 'application/pdf' });
                const url = window.URL.createObjectURL(blob);
                currentBlobUrl = url;
                setPdfUrl(url);
                setLoading(false);
            } catch (err) {
                if (!isMounted) return; // Don't update if unmounted

                console.error('Error loading PDF:', err);

                // Better error handling
                let errorMessage = 'Failed to load PDF';

                if (err.response) {
                    // Server responded with error
                    if (err.response.status === 404) {
                        errorMessage = 'PDF endpoint not found';
                    } else if (err.response.status === 401) {
                        errorMessage = 'Authentication required. Please log in again.';
                    } else if (err.response.status === 500) {
                        errorMessage = 'Server error while generating PDF';
                    } else {
                        errorMessage = err.response.data?.detail || err.response.data?.error || errorMessage;
                    }
                } else if (err.request) {
                    // Network error
                    errorMessage = 'Network error. Please check your connection and try again.';
                } else {
                    errorMessage = err.message || errorMessage;
                }

                setError(errorMessage);
                setLoading(false);
            }
        };

        fetchPDF();

        // Cleanup function
        return () => {
            isMounted = false;
            if (currentBlobUrl) {
                window.URL.revokeObjectURL(currentBlobUrl);
            }
        };
    }, [apiUrl]); // Only re-fetch when apiUrl changes (on refresh)

    if (loading) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                flexDirection: 'column',
                gap: '1rem'
            }}>
                <div className="spinner-border text-primary" role="status" style={{ width: '3rem', height: '3rem' }}>
                    <span className="visually-hidden">Loading PDF...</span>
                </div>
                <p className="text-muted">Generating PDF...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                flexDirection: 'column',
                gap: '1rem'
            }}>
                <div className="alert alert-danger" style={{ maxWidth: '600px' }}>
                    <h4 className="alert-heading">
                        <i className="bi bi-exclamation-triangle-fill me-2"></i>
                        Error Loading PDF
                    </h4>
                    <p>{error}</p>
                    <hr />
                    <button
                        className="btn btn-primary"
                        onClick={() => window.location.reload()}
                    >
                        <i className="bi bi-arrow-clockwise me-2"></i>
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div style={{ height: '100vh', width: '100vw', margin: 0, padding: 0 }}>
            {pdfUrl && (
                <iframe
                    src={pdfUrl}
                    style={{
                        width: '100%',
                        height: '100%',
                        border: 'none'
                    }}
                    title="PDF Viewer"
                />
            )}

            {/* Floating refresh button */}
            <button
                onClick={() => window.location.reload()}
                style={{
                    position: 'fixed',
                    bottom: '20px',
                    right: '20px',
                    zIndex: 1000,
                    backgroundColor: 'var(--primary-color)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '50%',
                    width: '60px',
                    height: '60px',
                    fontSize: '1.5rem',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }}
                title="Refresh PDF"
                aria-label="Refresh PDF"
            >
                <i className="bi bi-arrow-clockwise"></i>
            </button>
        </div>
    );
}
