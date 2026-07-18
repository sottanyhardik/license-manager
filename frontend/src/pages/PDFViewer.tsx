import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Loader2, RefreshCw, TriangleAlert } from "lucide-react";

import api from "../api/axios";
import { Button } from "@/components/ui/button";

export function normalizePdfApiPath(value: string | null): string | null {
    const trimmed = value?.trim();
    if (!trimmed) return null;
    if (Array.from(trimmed).some((char) => {
        const code = char.charCodeAt(0);
        return code <= 31 || code === 127;
    })) return null;
    if (/^[a-z][a-z\d+\-.]*:/i.test(trimmed)) return null;
    if (trimmed.startsWith("//") || trimmed.includes("\\")) return null;
    return trimmed;
}

/**
 * PDF Viewer — opens PDFs in a dedicated route that regenerates on refresh.
 * URL format: /pdf-viewer?url=/license-ledger/export/all/?params...
 */
export default function PDFViewer() {
    const [searchParams] = useSearchParams();
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const apiUrl = normalizePdfApiPath(searchParams.get("url"));

    useEffect(() => {
        let isMounted = true;
        let currentBlobUrl = null;

        const fetchPDF = async () => {
            if (!apiUrl) {
                if (isMounted) { setError("Invalid or missing PDF URL"); setLoading(false); }
                return;
            }
            try {
                if (isMounted) { setLoading(true); setError(null); setPdfUrl(null); }
                const response = await api.get(apiUrl, { responseType: "blob" });
                if (!isMounted) return;
                const blob = new Blob([response.data], { type: "application/pdf" });
                const url = window.URL.createObjectURL(blob);
                currentBlobUrl = url;
                setPdfUrl(url);
                setLoading(false);
            } catch (err: unknown) {
                if (!isMounted) return;
                console.error("Error loading PDF:", err);
                let errorMessage = "Failed to load PDF";
                const axiosErr = err as { response?: { status?: number; data?: { detail?: string; error?: string } }; request?: unknown; message?: string };
                if (axiosErr.response) {
                    if (axiosErr.response.status === 404) errorMessage = "PDF endpoint not found";
                    else if (axiosErr.response.status === 401) errorMessage = "Authentication required. Please log in again.";
                    else if (axiosErr.response.status === 500) errorMessage = "Server error while generating PDF";
                    else errorMessage = axiosErr.response.data?.detail || axiosErr.response.data?.error || errorMessage;
                } else if (axiosErr.request) {
                    errorMessage = "Network error. Please check your connection and try again.";
                } else if (axiosErr.message) {
                    errorMessage = axiosErr.message;
                }
                setError(errorMessage);
                setLoading(false);
            }
        };

        fetchPDF();
        return () => {
            isMounted = false;
            if (currentBlobUrl) window.URL.revokeObjectURL(currentBlobUrl);
        };
    }, [apiUrl]);

    if (loading) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-3 bg-background">
                <Loader2 className="size-9 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Generating PDF…</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background px-6">
                <div className="w-full max-w-lg rounded-lg border border-destructive/30 bg-destructive/10 p-5 text-destructive">
                    <div className="mb-2 flex items-center gap-2 text-base font-semibold">
                        <TriangleAlert className="size-5" />Error Loading PDF
                    </div>
                    <p className="mb-4 text-sm">{error}</p>
                    <Button variant="outline" onClick={() => window.location.reload()}>
                        <RefreshCw className="size-4" />Retry
                    </Button>
                </div>
            </div>
        );
    }

    return (
        <div className="m-0 h-screen w-screen p-0">
            {pdfUrl && <iframe src={pdfUrl} className="size-full border-none" title="PDF Viewer" />}
            <Button
                type="button"
                onClick={() => window.location.reload()}
                title="Refresh PDF"
                aria-label="Refresh PDF"
                className="fixed bottom-5 right-5 z-[1000] size-14 rounded-full shadow-lg transition-transform hover:scale-105 active:scale-95"
            >
                <RefreshCw className="size-6" />
            </Button>
        </div>
    );
}
