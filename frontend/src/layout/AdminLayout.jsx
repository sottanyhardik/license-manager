import TopNav from "../components/TopNav";
import TaskFAB from "../components/TaskFAB";
import {useNavigate} from "react-router-dom";
import {useState} from "react";
import {usePageTitle} from "../hooks/usePageTitle";

const QUICK_ACTIONS = [
    { to: '/licenses/create',        label: 'New License',   icon: 'bi-plus-circle',         primary: true  },
    { to: '/allotments/create',      label: 'New Allotment', icon: 'bi-plus-circle' },
    { to: '/masters/bill-of-entries/create', label: 'New BOE', icon: 'bi-plus-circle' },
    { to: '/reports/item-pivot',     label: 'Reports',       icon: 'bi-graph-up-arrow' },
];

export default function AdminLayout({children}) {
    const navigate = useNavigate();
    const [isInIframe] = useState(() => {
        if (typeof window === 'undefined') return false;
        try { return window.self !== window.top; } catch { return true; }
    });
    usePageTitle();

    return (
        <div className="d-flex flex-column" style={{minHeight: "100vh", background: "var(--surface-canvas)"}}>
            {!isInIframe && <TopNav/>}

            <main
                id="main-content"
                className="flex-grow-1"
                style={{ overflowY: 'auto' }}
            >
                <div
                    className="container-fluid"
                    style={{
                        padding: isInIframe ? '1rem 1.5rem' : undefined,
                        maxWidth: '100%',
                        paddingBottom: isInIframe ? '1rem' : undefined,
                    }}
                >
                    {/* ARIA live region for form validation announcements */}
                    <div
                        id="form-announcements"
                        role="status"
                        aria-live="polite"
                        aria-atomic="true"
                        className="visually-hidden"
                    ></div>
                    {children}
                </div>
            </main>

            {!isInIframe && (
                <footer
                    aria-label="Quick actions"
                    style={{
                        position: 'fixed',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        zIndex: 1000,
                        background: 'rgba(255, 255, 255, 0.82)',
                        backdropFilter: 'saturate(180%) blur(16px)',
                        WebkitBackdropFilter: 'saturate(180%) blur(16px)',
                        borderTop: '1px solid var(--border-subtle)',
                    }}
                >
                    <div
                        className="container-fluid d-flex align-items-center"
                        style={{
                            padding: '8px clamp(1rem, 4vw, 2rem)',
                            gap: 12,
                            flexWrap: 'wrap',
                        }}
                    >
                        <div className="d-flex" style={{ gap: 8, flexWrap: 'wrap', flex: 1, minWidth: 0 }}>
                            {QUICK_ACTIONS.map(a => (
                                <button
                                    key={a.to}
                                    type="button"
                                    onClick={() => navigate(a.to)}
                                    className={a.primary ? 'btn btn-primary btn-sm' : 'btn btn-outline-secondary btn-sm'}
                                    style={{ fontWeight: 500 }}
                                >
                                    <i className={`bi ${a.icon} me-1`} aria-hidden="true"></i>
                                    <span className="footer-action-label">{a.label}</span>
                                </button>
                            ))}
                        </div>
                        <small
                            style={{
                                color: 'var(--text-tertiary)',
                                fontSize: '0.78rem',
                                whiteSpace: 'nowrap',
                            }}
                        >
                            Built by Hardik Sottany
                        </small>
                    </div>
                </footer>
            )}

            {!isInIframe && <TaskFAB bottomOffset={84}/>}
        </div>
    );
}
