import { useEffect, useRef } from "react";
import { AlertTriangle, CheckCircle, Info, XOctagon } from "lucide-react";
import { cn } from "@/lib/utils";

// Severity → icon, icon container classes, confirm button classes
const SEVERITY_CONFIG = {
    danger: {
        Icon: XOctagon,
        iconCls: "bg-destructive/10 text-destructive",
        confirmCls: "bg-destructive text-white hover:bg-destructive/90",
    },
    warning: {
        Icon: AlertTriangle,
        iconCls: "bg-warning/10 text-warning",
        confirmCls: "bg-warning text-white hover:bg-warning/90",
    },
    info: {
        Icon: Info,
        iconCls: "bg-info/10 text-info",
        confirmCls: "bg-primary text-white hover:bg-primary/90",
    },
    success: {
        Icon: CheckCircle,
        iconCls: "bg-success/10 text-success",
        confirmCls: "bg-success text-white hover:bg-success/90",
    },
} as const;

type Severity = keyof typeof SEVERITY_CONFIG;

interface ConfirmDialogProps {
    show: boolean;
    title?: string;
    message?: string;
    /** One of "danger" | "warning" | "info" | "success"; falls back to "warning" */
    severity?: Severity | string;
    confirmText?: string;
    cancelText?: string;
    onConfirm: () => void;
    onCancel: () => void;
    showCancelButton?: boolean;
    /** Override CSS classes for the confirm button */
    confirmButtonClassName?: string;
    /** Override CSS classes for the cancel button */
    cancelButtonClassName?: string;
}

export const ConfirmDialog = ({
    show,
    title = "Confirm Action",
    message = "Are you sure you want to proceed?",
    severity = "warning",
    confirmText = "Confirm",
    cancelText = "Cancel",
    onConfirm,
    onCancel,
    showCancelButton = true,
    confirmButtonClassName = "",
    cancelButtonClassName = "",
}: ConfirmDialogProps) => {
    const dialogRef = useRef<HTMLDivElement>(null);
    const confirmButtonRef = useRef<HTMLButtonElement>(null);
    const previousFocusRef = useRef<Element | null>(null);
    const cfg = SEVERITY_CONFIG[severity as Severity] ?? SEVERITY_CONFIG.warning;
    const { Icon } = cfg;

    // Focus management: restore previous focus on close; focus confirm on open
    useEffect(() => {
        if (!show) return;
        previousFocusRef.current = document.activeElement;
        const t = setTimeout(() => confirmButtonRef.current?.focus(), 60);

        // Tab-trap within dialog
        const onTab = (e: KeyboardEvent) => {
            if (e.key !== "Tab" || !dialogRef.current) return;
            const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
                "button:not([disabled]), [tabindex]:not([tabindex='-1'])"
            );
            if (!focusable.length) return;
            const first = focusable[0], last = focusable[focusable.length - 1];
            if (e.shiftKey) {
                if (document.activeElement === first) { e.preventDefault(); last.focus(); }
            } else {
                if (document.activeElement === last) { e.preventDefault(); first.focus(); }
            }
        };
        document.addEventListener("keydown", onTab);
        return () => {
            clearTimeout(t);
            document.removeEventListener("keydown", onTab);
            (previousFocusRef.current as HTMLElement | null)?.focus();
        };
    }, [show]);

    // Escape = cancel, Enter = confirm
    useEffect(() => {
        if (!show) return;
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape") onCancel();
            else if (e.key === "Enter") onConfirm();
        };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, [show, onConfirm, onCancel]);

    // Prevent body scroll while open
    useEffect(() => {
        document.body.style.overflow = show ? "hidden" : "";
        return () => { document.body.style.overflow = ""; };
    }, [show]);

    if (!show) return null;

    return (
        /* Backdrop */
        <div
            className="fixed inset-0 z-[1060] flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.48)", backdropFilter: "blur(3px)", animation: "tb-fade-in 120ms ease both" }}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-message"
            onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
        >
            {/* Panel */}
            <div
                ref={dialogRef}
                className="w-full max-w-[420px] overflow-hidden rounded-2xl border border-border bg-card shadow-[0_24px_56px_rgba(0,0,0,0.18),0_8px_16px_rgba(0,0,0,0.10)]"
                style={{ animation: "tb-panel-enter 160ms var(--tb-ease) both" }}
            >
                {/* Body */}
                <div className="flex items-start gap-4 px-6 pb-5 pt-6">
                    {/* Severity icon */}
                    <span className={cn(
                        "flex size-10 shrink-0 items-center justify-center rounded-xl",
                        cfg.iconCls
                    )}>
                        <Icon className="size-5" strokeWidth={1.75} aria-hidden="true" />
                    </span>

                    {/* Text */}
                    <div className="min-w-0 flex-1">
                        <h5
                            id="confirm-dialog-title"
                            className="mb-1.5 text-[15px] font-semibold leading-tight tracking-tight text-foreground"
                        >
                            {title}
                        </h5>
                        <p
                            id="confirm-dialog-message"
                            className="text-[13.5px] leading-relaxed text-muted-foreground"
                        >
                            {message}
                        </p>
                    </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-2 border-t border-border/60 bg-muted/30 px-6 py-4">
                    {showCancelButton && (
                        <button
                            type="button"
                            onClick={onCancel}
                            className={cn(
                                "inline-flex h-9 min-w-[88px] items-center justify-center rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 cursor-pointer",
                                cancelButtonClassName
                            )}
                        >
                            {cancelText}
                        </button>
                    )}
                    <button
                        ref={confirmButtonRef}
                        type="button"
                        onClick={onConfirm}
                        className={cn(
                            "inline-flex h-9 min-w-[88px] items-center justify-center rounded-lg px-4 text-sm font-semibold shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 cursor-pointer",
                            confirmButtonClassName || cfg.confirmCls
                        )}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ConfirmDialog;
