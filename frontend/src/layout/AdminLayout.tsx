import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { usePageTitle } from "../hooks/usePageTitle";
import TopNav from "../components/TopNav";
import TaskFAB from "../components/TaskFAB";

const QUICK_ACTIONS = [
    { to: "/licenses/create",        label: "New License",   icon: "plus-circle-fill",   primary: true },
    { to: "/allotments/create",      label: "New Allotment", icon: "box-seam" },
    { to: "/bill-of-entries/create", label: "New BOE",       icon: "receipt" },
    { to: "/reports/item-pivot",     label: "Reports",       icon: "graph-up-arrow" },
];

export default function AdminLayout({ children }) {
    const navigate = useNavigate();
    const [isInIframe] = useState(() => {
        if (typeof window === "undefined") return false;
        try { return window.self !== window.top; } catch { return true; }
    });
    usePageTitle();

    return (
        <div style={{ minHeight: "100vh", background: "var(--tb-body-bg)", display: "flex", flexDirection: "column" }}>
            {!isInIframe && <TopNav />}

            <main id="main-content" style={{ flex: "1 1 auto", overflowY: "auto" }}>
                <div
                    className="container-fluid page-enter"
                    style={{
                        padding: isInIframe ? "16px 20px" : undefined,
                        maxWidth: "100%",
                        paddingBottom: isInIframe ? "16px" : undefined,
                    }}
                >
                    {/* ARIA live region for form validation announcements */}
                    <div
                        id="form-announcements"
                        role="status"
                        aria-live="polite"
                        aria-atomic="true"
                        className="visually-hidden"
                    />
                    {children}
                </div>
            </main>

            {!isInIframe && (
                <footer className="tb-app-footer" aria-label="Quick actions">
                    <div className="tb-app-footer-inner">
                        <div className="tb-app-footer-actions">
                            {QUICK_ACTIONS.map(a => (
                                <button
                                    key={a.to}
                                    type="button"
                                    onClick={() => navigate(a.to)}
                                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all duration-200 ${a.primary ? "bg-primary text-primary-foreground hover:bg-primary/90" : "border border-border bg-card text-muted-foreground hover:bg-muted"}`}
                                    style={{ fontSize: 12, height: 30, display: "inline-flex", alignItems: "center", gap: 5 }}
                                >
                                    <i className={`bi bi-${a.icon}`} aria-hidden="true" style={{ fontSize: 12 }} />
                                    <span className="footer-action-label">{a.label}</span>
                                </button>
                            ))}
                        </div>
                        <small className="tb-app-footer-meta">Built by Hardik Sottany</small>
                    </div>
                </footer>
            )}

            {!isInIframe && <TaskFAB bottomOffset={44} />}
        </div>
    );
}
