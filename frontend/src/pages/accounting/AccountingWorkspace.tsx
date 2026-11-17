import { lazy, Suspense } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { BookOpenCheck } from "lucide-react";

import { PageLoader } from "@/components/LoadingFallback";
import { Breadcrumbs } from "@/components/workspace/ModuleWorkspace";

import { AccountingProvider, currentFyLabel, useAccounting } from "./AccountingContext";
import { ACCOUNTING_GROUPS, activeSection } from "./sections";
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
const Masters = lazy(() => import("./Masters"));
const PartyLedgers = lazy(() => import("./Masters").then((m) => ({ default: m.PartyLedgers })));
const EntitySummary = lazy(() => import("./EntitySummary"));

/** Accounting / Group / Item [/ #id] (route-derived, so every screen has a way back). */
function useAccountingCrumbs(): { label: string; to?: string }[] {
    const { pathname } = useLocation();
    const active = activeSection(pathname);
    const crumbs: { label: string; to?: string }[] = [{ label: "Accounting", to: "/accounting/dashboard" }];
    if (!active) return crumbs;
    if (active.group.id !== "dashboard") crumbs.push({ label: active.group.label, to: active.group.items[0].to });
    crumbs.push({ label: active.item.label, to: active.item.to });
    const rest = pathname.slice(active.item.to.length).split("/").filter(Boolean);
    if (rest[0]) crumbs.push({ label: /^\d+$/.test(rest[0]) ? `#${rest[0]}` : rest.join(" ").replace(/-/g, " ").replace(/^\w/, (c) => c.toUpperCase()) });
    return crumbs;
}

function fyOptions(): string[] {
    const current = Number(currentFyLabel().slice(0, 4));
    return Array.from({ length: 6 }, (_, i) => current + 1 - i).map((y) => `${y}-${String(y + 1).slice(-2)}`);
}

function PeriodControls() {
    const { fy, setFy, fyBounds, range, setRange, fyRange } = useAccounting();
    const setEdge = (edge: "start" | "end", value: string) => setRange({ ...fyRange, [edge]: value || fyBounds[edge] });
    return (
        <>
            <label className="flex flex-col text-[11px] font-medium text-slate-500">
                Financial year
                <select className={inputCls} value={fy ?? ""} aria-label="Financial year" onChange={(e) => setFy(e.target.value)}>
                    {fyOptions().map((f) => <option key={f} value={f}>FY {f}</option>)}
                </select>
            </label>
            <label className="flex flex-col text-[11px] font-medium text-slate-500">
                From
                <input type="date" className={`${inputCls} w-36`} aria-label="From date" min={fyBounds.start} max={fyBounds.end}
                       value={fyRange.start} onChange={(e) => setEdge("start", e.target.value)} />
            </label>
            <label className="flex flex-col text-[11px] font-medium text-slate-500">
                To
                <input type="date" className={`${inputCls} w-36`} aria-label="To date" min={fyBounds.start} max={fyBounds.end}
                       value={fyRange.end} onChange={(e) => setEdge("end", e.target.value)} />
            </label>
            {range && (
                <button type="button" className="h-9 self-end rounded-md px-2 text-xs font-medium text-blue-700 hover:bg-blue-50"
                        onClick={() => setRange(null)}>Whole FY</button>
            )}
        </>
    );
}

function WorkspaceHeader() {
    const { entities, entityId, setEntityId, entity } = useAccounting();
    const { pathname } = useLocation();
    const crumbs = useAccountingCrumbs();
    const active = activeSection(pathname);
    const groupTab = (id: string) =>
        `whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${active?.group.id === id
            ? "border-blue-600 text-blue-700" : "border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900"}`;
    const subTab = (isActive: boolean) =>
        `whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium ${isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`;
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
                    <PeriodControls />
                </div>
            </div>
            <nav aria-label="Accounting sections" className="mt-3 flex gap-1 overflow-x-auto pb-px">
                {ACCOUNTING_GROUPS.map((g) => (
                    <Link key={g.id} to={g.items[0].to} className={groupTab(g.id)}
                          aria-current={active?.group.id === g.id ? "page" : undefined}>{g.label}</Link>
                ))}
            </nav>
            {active && active.group.items.length > 1 && (
                <nav aria-label={`${active.group.label} pages`} className="flex gap-1 overflow-x-auto py-2">
                    {active.group.items.map((i) => (
                        <Link key={i.to} to={i.to} className={subTab(active.item.to === i.to)}
                              aria-current={active.item.to === i.to ? "page" : undefined}>{i.label}</Link>
                    ))}
                </nav>
            )}
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
                <Route path="masters/*" element={<NeedsEntity><Masters /></NeedsEntity>} />
                <Route path="trades" element={<NeedsEntity><TradeTracking /></NeedsEntity>} />
                <Route path="invoices/*" element={<NeedsEntity><Invoices /></NeedsEntity>} />
                <Route path="payments" element={<NeedsEntity><Payments /></NeedsEntity>} />
                <Route path="vouchers/*" element={<NeedsEntity><Vouchers /></NeedsEntity>} />
                <Route path="party-ledger" element={<NeedsEntity><PartyLedger /></NeedsEntity>} />
                <Route path="ledgers/customers" element={<NeedsEntity><PartyLedgers side="customers" /></NeedsEntity>} />
                <Route path="ledgers/suppliers" element={<NeedsEntity><PartyLedgers side="suppliers" /></NeedsEntity>} />
                <Route path="banking/*" element={<NeedsEntity><Banking /></NeedsEntity>} />
                <Route path="reports/*" element={<NeedsEntity><Reports /></NeedsEntity>} />
                <Route path="entities" element={<NeedsEntity><EntitySummary /></NeedsEntity>} />
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
