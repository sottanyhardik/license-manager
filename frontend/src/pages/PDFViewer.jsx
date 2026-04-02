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
        const fetchPDF = async () => {
            if (!apiUrl) {
                setError('No PDF URL provided');
                setLoading(false);
                return;
            }

            try {
                setLoading(true);
                setError(null);

                const response = await api.get(apiUrl, {
                    responseType: 'blob'
                });

                const blob = new Blob([response.data], { type: 'application/pdf' });
                const url = window.URL.createObjectURL(blob);
                setPdfUrl(url);
                setLoading(false);
            } catch (err) {
                console.error('Error loading PDF:', err);
                setError(err.response?.data?.detail || 'Failed to load PDF');
                setLoading(false);
            }
        };

        fetchPDF();

        // Cleanup blob URL on unmount
        return () => {
            if (pdfUrl) {
                window.URL.revokeObjectURL(pdfUrl);
            }
        };
    }, [apiUrl]); // Re-fetch when apiUrl changes (on refresh)

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
                    backgroundColor: '#0d6efd',
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
