import { useEffect, useRef } from "react";

const SEVERITY = {
    danger:  { icon: "exclamation-triangle-fill", tone: "danger",  confirmVariant: "btn-danger" },
    warning: { icon: "exclamation-triangle",       tone: "warning", confirmVariant: "btn-warning" },
    info:    { icon: "info-circle",                tone: "info",    confirmVariant: "btn-primary" },
    success: { icon: "check-circle",               tone: "success", confirmVariant: "btn-success" },
};

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
}) => {
    const dialogRef = useRef(null);
    const confirmButtonRef = useRef(null);
    const previousFocusRef = useRef(null);
    const cfg = SEVERITY[severity] || SEVERITY.warning;

    useEffect(() => {
        if (!show) return;
        previousFocusRef.current = document.activeElement;
        const t = setTimeout(() => confirmButtonRef.current?.focus(), 60);

        const onTab = (e) => {
            if (e.key !== "Tab" || !dialogRef.current) return;
            const focusable = dialogRef.current.querySelectorAll(
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
            previousFocusRef.current?.focus();
        };
    }, [show]);

    useEffect(() => {
        if (!show) return;
        const handler = (e) => {
            if (e.key === "Escape") onCancel();
            else if (e.key === "Enter") onConfirm();
        };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, [show, onConfirm, onCancel]);

    useEffect(() => {
        document.body.style.overflow = show ? "hidden" : "";
        return () => { document.body.style.overflow = ""; };
    }, [show]);

    if (!show) return null;

    const iconBg = {
        danger:  "var(--tb-danger-soft)",
        warning: "var(--tb-warning-soft)",
        info:    "var(--tb-info-soft)",
        success: "var(--tb-success-soft)",
    }[severity] || "var(--tb-sunken)";

    const iconColor = {
        danger:  "var(--tb-danger-text)",
        warning: "var(--tb-warning-text)",
        info:    "var(--tb-info-text)",
        success: "var(--tb-success-text)",
    }[severity] || "var(--tb-text-secondary)";

    return (
        <div
            style={{
                position: "fixed",
                inset: 0,
                background: "rgba(0,0,0,0.48)",
                zIndex: 1060,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 16,
                backdropFilter: "blur(2px)",
                animation: "tb-fade-in 120ms ease both",
            }}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            aria-describedby="confirm-dialog-message"
            onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
        >
            <div
                ref={dialogRef}
                style={{
                    background: "var(--tb-card-bg)",
                    border: "1px solid var(--tb-border)",
                    borderRadius: "var(--tb-r-xl)",
                    boxShadow: "var(--tb-shadow-overlay)",
                    maxWidth: 420,
                    width: "100%",
                    animation: "tb-panel-enter 160ms var(--tb-ease) both",
                    overflow: "hidden",
                }}
            >
                {/* Body */}
                <div style={{ padding: "24px 24px 20px", display: "flex", gap: 16, alignItems: "flex-start" }}>
                    <div
                        style={{
                            width: 40,
                            height: 40,
                            borderRadius: "var(--tb-r-md)",
                            background: iconBg,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 18,
                            color: iconColor,
                            flexShrink: 0,
                        }}
                    >
                        <i className={`bi bi-${cfg.icon}`} aria-hidden="true" />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <h5
                            id="confirm-dialog-title"
                            style={{
                                fontSize: 15,
                                fontWeight: 600,
                                color: "var(--tb-text)",
                                margin: "0 0 6px",
                                letterSpacing: "-0.015em",
                            }}
                        >
                            {title}
                        </h5>
                        <p
                            id="confirm-dialog-message"
                            style={{
                                fontSize: 13.5,
                                color: "var(--tb-text-secondary)",
                                margin: 0,
                                lineHeight: 1.6,
                            }}
                        >
                            {message}
                        </p>
                    </div>
                </div>

                {/* Footer */}
                <div
                    style={{
                        padding: "12px 24px 20px",
                        display: "flex",
                        gap: 8,
                        justifyContent: "flex-end",
                    }}
                >
                    {showCancelButton && (
                        <button
                            type="button"
                            className={`btn btn-sm ${cancelButtonClassName || "btn-outline-secondary"}`}
                            onClick={onCancel}
                            style={{ minWidth: 80, height: 34 }}
                        >
                            {cancelText}
                        </button>
                    )}
                    <button
                        ref={confirmButtonRef}
                        type="button"
                        className={`btn btn-sm ${confirmButtonClassName || cfg.confirmVariant}`}
                        onClick={onConfirm}
                        style={{ minWidth: 80, height: 34 }}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ConfirmDialog;
