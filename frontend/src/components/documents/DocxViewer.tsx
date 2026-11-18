/**
 * DocxViewer: renders a stored .docx inside the app (headings, paragraphs,
 * tables, images, headers/footers and page breaks) with zoom, page navigation
 * and download.
 *
 * Security: the file is fetched through the authenticated media endpoint
 * (`/api/media/…`, ProtectedMediaView) with the shared axios instance — never a
 * public `/media/` URL or an external origin. The original bytes are only read:
 * the download hands the user the exact file the server sent. `docx-preview`
 * builds DOM nodes from the document XML (no HTML/script interpretation);
 * hyperlinks are additionally restricted to http(s)/mailto/in-document anchors.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, Minus, Plus, RotateCcw } from "lucide-react";
import api from "@/api/axios";
import { EmptyState, InlineError, LoadingState } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { normalizeAuthedFilePath } from "@/utils/documentDownload";
import { sanitizeRenderedLinks } from "./sanitizeRenderedLinks";

export interface DocxViewerProps {
    /** Path relative to the API base, e.g. `/media/tl/LETTER.docx` (see `toProtectedMediaPath`). */
    path: string;
    /** Download file name (defaults to the path's basename). */
    filename?: string;
}

const ZOOM_STEPS = [0.5, 0.67, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];

function httpStatus(error: unknown): number | undefined {
    return (error as { response?: { status?: number } })?.response?.status;
}

export function DocxViewer({ path, filename }: DocxViewerProps) {
    const safePath = normalizeAuthedFilePath(path);
    const name = filename ?? decodeURIComponent(safePath.split("/").pop() || "document.docx");
    const scrollRef = useRef<HTMLDivElement>(null);
    const bodyRef = useRef<HTMLDivElement>(null);
    const [renderError, setRenderError] = useState<unknown>(null);
    const [rendering, setRendering] = useState(true);
    const [pages, setPages] = useState(0);
    const [page, setPage] = useState(1);
    const [zoomIndex, setZoomIndex] = useState(ZOOM_STEPS.indexOf(1));
    const zoom = ZOOM_STEPS[zoomIndex];

    const file = useQuery({
        queryKey: ["docx-file", safePath],
        queryFn: async ({ signal }) => (await api.get(safePath, { responseType: "blob", signal })).data as Blob,
        retry: false,
        staleTime: 5 * 60_000,
    });

    useEffect(() => {
        const blob = file.data;
        const body = bodyRef.current;
        if (!blob || !body) return;
        let cancelled = false;
        setRendering(true);
        setRenderError(null);
        (async () => {
            try {
                const { renderAsync } = await import("docx-preview");
                if (cancelled) return;
                body.replaceChildren();
                await renderAsync(blob, body, undefined, {
                    className: "docx",
                    inWrapper: true,
                    breakPages: true,
                    renderHeaders: true,
                    renderFooters: true,
                    renderFootnotes: true,
                    // Images as data: URLs — no object URLs to leak or revoke.
                    useBase64URL: true,
                });
                if (cancelled) return;
                sanitizeRenderedLinks(body);
                setPages(body.querySelectorAll("section.docx").length);
                setPage(1);
            } catch (error) {
                if (!cancelled) setRenderError(error);
            } finally {
                if (!cancelled) setRendering(false);
            }
        })();
        return () => { cancelled = true; };
    }, [file.data]);

    // Current page = the last page whose top has scrolled past the viewport's upper third.
    const onScroll = useCallback(() => {
        const scroller = scrollRef.current;
        const body = bodyRef.current;
        if (!scroller || !body) return;
        const limit = scroller.getBoundingClientRect().top + scroller.clientHeight / 3;
        let current = 1;
        body.querySelectorAll("section.docx").forEach((section, index) => {
            if (section.getBoundingClientRect().top <= limit) current = index + 1;
        });
        setPage(current);
    }, []);

    const goTo = (target: number) => {
        const next = Math.min(Math.max(target, 1), pages);
        bodyRef.current?.querySelectorAll("section.docx")[next - 1]?.scrollIntoView({ block: "start", behavior: "smooth" });
        setPage(next);
    };

    const download = () => {
        if (!file.data) return;
        const url = URL.createObjectURL(file.data);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = name;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
    };

    if (file.isPending) return <LoadingState variant="spinner" label="Loading document" />;
    if (file.isError) {
        const status = httpStatus(file.error);
        if (status === 404) return <EmptyState title="Document file is missing" description={`“${name}” is recorded on this record but the file is not on the server.`} />;
        if (status === 403) return <EmptyState title="No access to this document" description="Your role cannot open this file." />;
        return <InlineError error={file.error} onRetry={() => { void file.refetch(); }} title="Could not load the document" />;
    }

    return (
        <div className="flex min-w-0 flex-col gap-2" data-testid="docx-viewer">
            <div role="toolbar" aria-label="Document controls" className="flex flex-wrap items-center gap-1.5">
                <Button type="button" size="sm" variant="outline" aria-label="Zoom out" disabled={zoomIndex === 0} onClick={() => setZoomIndex(i => i - 1)}>
                    <Minus className="size-4" aria-hidden="true" />
                </Button>
                <span className="w-12 text-center text-xs tabular-nums text-muted-foreground" aria-live="polite">{Math.round(zoom * 100)}%</span>
                <Button type="button" size="sm" variant="outline" aria-label="Zoom in" disabled={zoomIndex === ZOOM_STEPS.length - 1} onClick={() => setZoomIndex(i => i + 1)}>
                    <Plus className="size-4" aria-hidden="true" />
                </Button>
                <Button type="button" size="sm" variant="ghost" aria-label="Reset zoom" disabled={zoom === 1} onClick={() => setZoomIndex(ZOOM_STEPS.indexOf(1))}>
                    <RotateCcw className="size-4" aria-hidden="true" />
                </Button>
                {pages > 1 && (
                    <div className="ml-1 flex items-center gap-1">
                        <Button type="button" size="sm" variant="outline" aria-label="Previous page" disabled={page <= 1} onClick={() => goTo(page - 1)}>
                            <ChevronLeft className="size-4" aria-hidden="true" />
                        </Button>
                        <span className="text-xs tabular-nums text-muted-foreground">Page {page} of {pages}</span>
                        <Button type="button" size="sm" variant="outline" aria-label="Next page" disabled={page >= pages} onClick={() => goTo(page + 1)}>
                            <ChevronRight className="size-4" aria-hidden="true" />
                        </Button>
                    </div>
                )}
                <Button type="button" size="sm" variant="outline" className="ml-auto" onClick={download}>
                    <Download className="size-4" aria-hidden="true" /> Download
                </Button>
            </div>

            {renderError !== null && (
                <EmptyState
                    title="Could not render this document"
                    description="The file may be damaged or not a Word (.docx) document. You can still download the original."
                />
            )}
            {rendering && renderError === null && <LoadingState variant="spinner" label="Rendering document" />}
            <div
                ref={scrollRef}
                onScroll={onScroll}
                hidden={renderError !== null}
                className="max-h-[75vh] min-h-48 overflow-auto rounded-lg border border-border bg-muted/40"
            >
                <div ref={bodyRef} aria-label={`${name} preview`} role="document" style={{ zoom }} />
            </div>
        </div>
    );
}
