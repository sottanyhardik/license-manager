import { useNavigate, useLocation } from "react-router-dom";
import { useState } from "react";
import { BarChart3, Boxes, FilePlus2, Receipt, type LucideIcon } from "lucide-react";
import { usePageTitle } from "../hooks/usePageTitle";
import { useParsingStatus } from "@/context/ParsingStatusContext";
import TopNav from "../components/TopNav";
import TaskFAB from "../components/TaskFAB";
import ParsingStatusDisplay from "../components/ParsingStatusDisplay";
import { cn } from "@/lib/utils";

interface QuickAction { to: string; label: string; icon: LucideIcon; primary?: boolean }

/** Shortcuts shown only on the Dashboard; register/detail pages carry their own header actions. */
const QUICK_ACTIONS: QuickAction[] = [
    { to: "/licenses/create",        label: "New License",   icon: FilePlus2, primary: true },
    { to: "/allotments/create",      label: "New Allotment", icon: Boxes },
    { to: "/bill-of-entries/create", label: "New BOE",       icon: Receipt },
    { to: "/reports/item-pivot",     label: "Reports",       icon: BarChart3 },
];

/** Routes with a sticky form footer: the floating Tasks button is hidden there so it can never cover Save/Cancel. */
const FORM_ROUTE = /\/(create|edit)(\/|$)|^\/bill-of-entries\/[^/]+$|\/allocate$|\/generate-transfer-letter$/;

export default function AdminLayout({ children }) {
    const navigate = useNavigate();
    const { pathname } = useLocation();
    const { parsingStatus } = useParsingStatus();
    const isDashboard = pathname === "/dashboard";
    const showFooter = isDashboard || Boolean(parsingStatus);
    const showFab = !FORM_ROUTE.test(pathname);
    const [isInIframe] = useState(() => {
        if (typeof window === "undefined") return false;
        try { return window.self !== window.top; } catch { return true; }
    });
    usePageTitle();

    return (
        <div className="app-shell app-shell--admin flex min-h-screen flex-col bg-background">
            {!isInIframe && <TopNav />}

            <main id="main-content" className={cn("app-shell__main flex-1 overflow-y-auto", showFab && !isInIframe && "pb-16")} tabIndex={-1}>
                <div
                    className={[
                        "app-shell__content app-shell__content--admin page-enter mx-auto w-full max-w-[1920px]",
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

            {!isInIframe && showFooter && (
                <footer
                    className="border-t border-border/60 bg-card pb-[env(safe-area-inset-bottom)]"
                    aria-label="Quick actions and status"
                >
                    <div className="flex flex-col gap-2 px-4 py-2">
                        <ParsingStatusDisplay />
                        {isDashboard && (
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-1.5">
                                    {QUICK_ACTIONS.map(({ to, label, icon: ActionIcon, primary }) => (
                                        <button
                                            key={to}
                                            type="button"
                                            onClick={() => navigate(to)}
                                            className={cn(
                                                "inline-flex h-8 items-center gap-2 rounded-lg px-3 text-xs font-semibold shadow-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                                primary
                                                    ? "bg-primary text-primary-foreground hover:bg-primary/90"
                                                    : "border border-border bg-card text-foreground hover:bg-accent hover:text-accent-foreground",
                                            )}
                                        >
                                            <ActionIcon className="size-4" aria-hidden="true" />
                                            <span className="hidden sm:inline">{label}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </footer>
            )}

            {!isInIframe && showFab && <TaskFAB />}
        </div>
    );
}
