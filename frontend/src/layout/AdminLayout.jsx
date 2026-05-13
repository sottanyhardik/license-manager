import TopNav from "../components/TopNav";
import TaskFAB from "../components/TaskFAB";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { usePageTitle } from "../hooks/usePageTitle";

const QUICK_ACTIONS = [
    { to: "/licenses/create",        label: "New License",   icon: "bi-plus-circle",         primary: true },
    { to: "/allotments/create",      label: "New Allotment", icon: "bi-plus-circle" },
    { to: "/bill-of-entries/create", label: "New BOE",       icon: "bi-plus-circle" },
    { to: "/reports/item-pivot",     label: "Reports",       icon: "bi-graph-up-arrow" },
];

export default function AdminLayout({ children }) {
    const navigate = useNavigate();
    const [isInIframe] = useState(() => {
        if (typeof window === "undefined") return false;
        try { return window.self !== window.top; } catch { return true; }
    });
    usePageTitle();

    return (
        <div className="d-flex flex-column" style={{ minHeight: "100vh", background: "var(--tb-body-bg)" }}>
            {!isInIframe && <TopNav />}

            <main id="main-content" className="flex-grow-1" style={{ overflowY: "auto" }}>
                <div
                    className="container-fluid"
                    style={{
                        padding: isInIframe ? "1rem 1.5rem" : undefined,
                        maxWidth: "100%",
                        paddingBottom: isInIframe ? "1rem" : undefined,
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
                                    className={a.primary ? "btn btn-primary btn-sm" : "btn btn-outline-secondary btn-sm"}
                                >
                                    <i className={`bi ${a.icon} me-1`} aria-hidden="true" />
                                    <span className="footer-action-label">{a.label}</span>
                                </button>
                            ))}
                        </div>
                        <small className="tb-app-footer-meta">Built by Hardik Sottany</small>
                    </div>
                </footer>
            )}

            {!isInIframe && <TaskFAB bottomOffset={84} />}
        </div>
    );
}
