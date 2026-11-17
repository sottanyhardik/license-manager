import { lazy, Suspense } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { BookOpenCheck } from "lucide-react";

import { PageLoader } from "@/components/LoadingFallback";
import { Breadcrumbs } from "@/components/workspace/ModuleWorkspace";

import { AccountingProvider, currentFyLabel, useAccounting } from "./AccountingContext";
import { inputCls, NoEntity } from "./ui";

const Dashboard = lazy(() => import("./AccountingDashboard"));
const TradeTracking = lazy(() => import("./TradeTracking"));
const Vouchers = lazy(() => import("./Vouchers"));
const Invoices = lazy(() => import("./Invoices"));
const Payments = lazy(() => import("./Payments"));
const PartyLedger = lazy(() => import("./PartyLedger"));
const Banking = lazy(() => import("./Banking"));
const Reports = lazy(() => import("./Reports"));
const Loans = lazy(() => import("./Loans"));
const Migration = lazy(() => import("./MigrationCenter"));
const Setup = lazy(() => import("./Setup"));

const SECTIONS = [
    { to: "dashboard", label: "Dashboard" },
    { to: "trades", label: "Trade → Invoice" },
    { to: "invoices", label: "Bills & Expenses" },
    { to: "payments", label: "Payments" },
    { to: "vouchers", label: "Vouchers" },
    { to: "party-ledger", label: "Party Ledger" },
    { to: "banking", label: "Banking" },
    { to: "reports", label: "Reports" },
    { to: "loans", label: "Loans" },
    { to: "migration", label: "Migration" },
    { to: "setup", label: "Setup" },
];

const SUBPAGE_LABEL: Record<string, string> = {
    new: "New", workbench: "Statements & reconciliation", suspense: "Suspense",
    "trial-balance": "Trial Balance", "profit-loss": "Profit & Loss", "balance-sheet": "Balance Sheet",
    "cash-flow": "Cash Flow", "general-ledger": "General Ledger", "receivables-ageing": "Receivables Ageing",
    "payables-ageing": "Payables Ageing", register: "Registers", gst: "GST", tds: "TDS",
    "trade-profitability": "Trade Profitability", "bank-book": "Bank Book", "cash-book": "Cash Book",
    consolidated: "Consolidated",
};

/** Accounting / Section / Sub-page (route-derived, so every screen has a way back). */
function useAccountingCrumbs(): { label: string; to?: string }[] {
    const { pathname } = useLocation();
    const [, , section, sub, detail] = pathname.split("/");
    const sec = SECTIONS.find((s) => s.to === section);
    const crumbs: { label: string; to?: string }[] = [{ label: "Accounting", to: "/accounting/dashboard" }];
    if (sec) crumbs.push({ label: sec.label, to: `/accounting/${sec.to}` });
    if (sub) {
        const label = SUBPAGE_LABEL[sub] ?? (/^\d+$/.test(sub) ? `#${sub}` : sub.replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase()));
        crumbs.push({ label, to: `/accounting/${section}/${sub}` });
    }
    if (detail && /^\d+$/.test(detail)) crumbs.push({ label: `#${detail}` });
    return crumbs;
}

function fyOptions(): string[] {
    const current = Number(currentFyLabel().slice(0, 4));
    return Array.from({ length: 6 }, (_, i) => current + 1 - i).map((y) => `${y}-${String(y + 1).slice(-2)}`);
}

function WorkspaceHeader() {
    const { entities, entityId, setEntityId, fy, setFy, entity } = useAccounting();
    const crumbs = useAccountingCrumbs();
    return (
        <div className="-mx-4 mb-4 border-b border-slate-200 bg-white/90 px-4 pt-3 backdrop-blur sm:sticky sm:top-0 sm:z-20">
            <div className="flex flex-wrap items-end justify-between gap-3">
                <div className="flex items-center gap-2">
                    <span className="grid size-9 place-items-center rounded-lg bg-slate-900 text-white">
                        <BookOpenCheck className="size-5" aria-hidden />
                    </span>
                    <div>
                        <Breadcrumbs items={crumbs} />
                        <h1 className="text-lg font-semibold leading-tight text-slate-900">{entity?.name ?? "Books"}</h1>
                    </div>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                    <label className="flex flex-col text-[11px] font-medium text-slate-500">
                        Entity
                        <select className={inputCls} value={entityId ?? ""} aria-label="Entity"
                                onChange={(e) => setEntityId(e.target.value ? Number(e.target.value) : null)}>
                            {entities.length === 0 && <option value="">No books</option>}
                            {entities.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
                        </select>
                    </label>
                    <label className="flex flex-col text-[11px] font-medium text-slate-500">
                        Financial year
                        <select className={inputCls} value={fy ?? ""} aria-label="Financial year"
                                onChange={(e) => setFy(e.target.value)}>
                            {fyOptions().map((f) => <option key={f} value={f}>FY {f}</option>)}
                        </select>
                    </label>
                </div>
            </div>
            <nav aria-label="Accounting sections" className="mt-3 flex gap-1 overflow-x-auto pb-px">
                {SECTIONS.map((s) => (
                    <NavLink key={s.to} to={`/accounting/${s.to}`}
                             className={({ isActive }) =>
                                 `whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${isActive
                                     ? "border-blue-600 text-blue-700" : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900"}`}>
                        {s.label}
                    </NavLink>
                ))}
            </nav>
        </div>
    );
}

function NeedsEntity({ children }: { children: React.ReactNode }) {
    const { entityId, isLoading } = useAccounting();
    if (isLoading) return <PageLoader />;
    if (!entityId) return <NoEntity />;
    return <>{children}</>;
}

function WorkspaceRoutes() {
    const { entityId } = useAccounting();
    // Keyed by entity: switching entity remounts every page, so no draft (bank account, party,
    // allocations, confirmation text) can leak from one entity's books into another's.
    return (
        <Suspense fallback={<PageLoader />}>
            <Routes key={entityId ?? "none"}>
                        <Route index element={<Navigate to="dashboard" replace />} />
                        <Route path="dashboard" element={<NeedsEntity><Dashboard /></NeedsEntity>} />
                        <Route path="trades" element={<NeedsEntity><TradeTracking /></NeedsEntity>} />
                        <Route path="invoices/*" element={<NeedsEntity><Invoices /></NeedsEntity>} />
                        <Route path="payments" element={<NeedsEntity><Payments /></NeedsEntity>} />
                        <Route path="vouchers/*" element={<NeedsEntity><Vouchers /></NeedsEntity>} />
                        <Route path="party-ledger" element={<NeedsEntity><PartyLedger /></NeedsEntity>} />
                        <Route path="banking/*" element={<NeedsEntity><Banking /></NeedsEntity>} />
                        <Route path="reports/*" element={<NeedsEntity><Reports /></NeedsEntity>} />
                        <Route path="loans" element={<NeedsEntity><Loans /></NeedsEntity>} />
                        <Route path="migration" element={<NeedsEntity><Migration /></NeedsEntity>} />
                        <Route path="setup" element={<Setup />} />
                        <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Routes>
        </Suspense>
    );
}

export default function AccountingWorkspace() {
    return (
        <AccountingProvider>
            <div className="px-4 pb-10">
                <WorkspaceHeader />
                <WorkspaceRoutes />
            </div>
        </AccountingProvider>
    );
}
