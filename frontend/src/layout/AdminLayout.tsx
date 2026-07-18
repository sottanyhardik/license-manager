import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { usePageTitle } from "../hooks/usePageTitle";
import TopNav from "../components/TopNav";
import TaskFAB from "../components/TaskFAB";
import Icon from "@/components/Icon";

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
        <div className="flex min-h-screen flex-col bg-background">
            {!isInIframe && <TopNav />}

            <main id="main-content" className="flex-1 overflow-y-auto">
                <div
                    className={[
                        "page-enter mx-auto w-full max-w-[100%]",
                        isInIframe ? "px-5 py-4" : "container-fluid",
                    ].join(" ")}
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
                <footer
                    className="sticky bottom-0 z-40 border-t border-border/60 bg-card/95 backdrop-blur-sm"
                    aria-label="Quick actions"
                    style={{ height: 44 }}
                >
                    <div className="flex h-full items-center justify-between px-4">
                        {/* Quick-create actions */}
                        <div className="flex items-center gap-1.5">
                            {QUICK_ACTIONS.map(a => (
                                <button
                                    key={a.to}
                                    type="button"
                                    onClick={() => navigate(a.to)}
                                    className={[
                                        "inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-[11.5px] font-semibold transition-all duration-150",
                                        a.primary
                                            ? "bg-primary text-primary-foreground hover:bg-primary/90 active:scale-[0.97]"
                                            : "border border-border bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
                                    ].join(" ")}
                                >
                                    <Icon name={a.icon} className="size-3" aria-hidden="true" />
                                    <span className="footer-action-label">{a.label}</span>
                                </button>
                            ))}
                        </div>
                        {/* Subtle meta text */}
                        <span className="hidden text-[10.5px] text-muted-foreground/40 sm:block">
                            License Manager
                        </span>
                    </div>
                </footer>
            )}

            {!isInIframe && <TaskFAB bottomOffset={44} />}
        </div>
    );
}
