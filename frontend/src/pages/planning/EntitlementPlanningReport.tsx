import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Download, Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InlineError, LoadingState } from "@/components/shared";
import { formatIndianNumber } from "@/utils/numberFormatter";
import {
    downloadEntitlementPlanXlsx,
    fetchEntitlementPlan,
    type DebitRow,
    type EntitlementAfterRow,
    type EntitlementPlan,
} from "@/api/entitlementPlanApi";

/** Display only — every figure is computed by the backend; nothing is recalculated here. */
const fmt = (value: string | null | undefined, decimals = 2) =>
    value === null || value === undefined || value === "" ? "—" : formatIndianNumber(value, decimals);
const isNegative = (value?: string | null) => !!value && Number(value) < 0;
const num = "px-2 py-1.5 text-right tabular-nums whitespace-nowrap";
const anchorId = (key: string) => `entitlement-${key.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;

const COMPONENT_LABELS: Record<string, string> = {
    RELEASED_TO_RESIDUAL: "Released to residual entitlement (actual debit rate below plan)",
    RECEIVED_FROM_OTHER_ENTITLEMENTS: "Received from other entitlements",
    OTHER_AUTHORITATIVE_ADJUSTMENTS: "Other authoritative adjustments",
    UNPLANNED_ABOVE_MAX_PRICE: "Not planned (above maximum unit price)",
    UNPLANNED_OPENING_CIF: "Licence CIF not planned at opening",
};

function isPlan(value: unknown): value is EntitlementPlan {
    return !!value && typeof value === "object" && "opening" in value && "after" in value;
}

export function EntitlementPlanningReport({ licenseNumber, sion }: { licenseNumber: string; sion: string }) {
    const [plan, setPlan] = useState<EntitlementPlan | null>(null);
    const [error, setError] = useState<unknown>(null);
    const [loading, setLoading] = useState(true);

    const load = useCallback(() => {
        setLoading(true);
        setError(null);
        fetchEntitlementPlan(licenseNumber, sion)
            .then((data) => (isPlan(data) ? setPlan(data) : setError(new Error("Unexpected planning response."))))
            .catch(setError)
            .finally(() => setLoading(false));
    }, [licenseNumber, sion]);
    useEffect(load, [load]);

    if (loading) return <LoadingState variant="skeleton-rows" label="Loading licence planning" />;
    if (error || !plan) return <InlineError title="Licence planning unavailable" error={error} onRetry={load} />;
    return <PlanView plan={plan} />;
}

export function PlanView({ plan }: { plan: EntitlementPlan }) {
    return (
        <section aria-label="Licence entitlement planning" className="space-y-4 rounded-lg border bg-card p-3 print:border-0">
            <header className="flex flex-wrap items-start justify-between gap-2">
                <div>
                    <h2 className="text-base font-semibold">Licence Planning · {plan.licence_number} · {plan.sion}</h2>
                    <p className="text-xs text-muted-foreground">Read-only preview from the licence's recorded BOE debits and allotments. Nothing is posted.</p>
                </div>
                <div className="flex gap-2 print:hidden">
                    <Button size="sm" variant="outline" onClick={() => downloadEntitlementPlanXlsx(plan.licence_number, plan.sion)}><Download className="size-3.5" />Excel</Button>
                    <Button size="sm" variant="outline" onClick={() => window.print()}><Printer className="size-3.5" />Print / PDF</Button>
                </div>
            </header>
            <Summary plan={plan} />
            <Issues plan={plan} />
            <OpeningTable plan={plan} />
            <AfterTable plan={plan} />
        </section>
    );
}

function Summary({ plan }: { plan: EntitlementPlan }) {
    const reconciled = plan.reconciliation.status === "RECONCILED";
    const stats: [string, string][] = [
        ["Opening CIF", fmt(plan.opening.total_cif)],
        ["BOE debited CIF", fmt(plan.totals.boe_debit_cif)],
        ["Outstanding allotment CIF", fmt(plan.totals.allotment_cif)],
        ["Remaining licence CIF", fmt(plan.after.remaining_licence_cif)],
    ];
    const splitGroups = plan.opening.groups.filter((g) => g.split.length > 1);
    return (
        <div aria-label="Licence Planning Summary" className="space-y-3">
            <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
                {stats.map(([label, value]) => <div key={label} className="rounded border px-2 py-1.5"><dt className="text-xs text-muted-foreground">{label}</dt><dd className="font-semibold tabular-nums">{value}</dd></div>)}
                <div className="rounded border px-2 py-1.5"><dt className="text-xs text-muted-foreground">Reconciliation</dt><dd><Badge variant={reconciled ? "secondary" : "destructive"}>{reconciled ? "Reconciled" : "Needs attention"}</Badge></dd></div>
            </dl>
            <ul className="flex flex-wrap gap-2 text-xs" aria-label="Entitlement balances">
                {plan.after.entitlements.map((e) => (
                    <li key={e.entitlement}>
                        <a href={`#${anchorId(e.entitlement)}`} className="block rounded border px-2 py-1 hover:bg-muted">
                            <span className="font-medium">{e.label}</span>{" "}
                            <span className="text-muted-foreground">{fmt(e.opening.quantity)} → </span>
                            <span className={isNegative(e.balance.quantity) ? "font-semibold text-destructive" : "font-semibold"}>{fmt(e.balance.quantity)}</span>
                            <span className="text-muted-foreground"> qty · </span>
                            <span className={isNegative(e.balance.cif) ? "font-semibold text-destructive" : "font-semibold"}>{fmt(e.balance.cif)}</span>
                            <span className="text-muted-foreground"> CIF</span>
                        </a>
                    </li>
                ))}
            </ul>
            {splitGroups.map((g) => (
                <div key={g.group} className="text-xs">
                    <p className="mb-1 text-muted-foreground">{g.label} split · {fmt(g.quantity)} qty{g.reconciles ? "" : " · does not reconcile"}</p>
                    <div className="flex h-5 overflow-hidden rounded border" role="img" aria-label={`${g.label} split ${g.split.map((s) => `${s.label} ${s.percentage}%`).join(", ")}`}>
                        {g.split.map((s, i) => (
                            <div key={s.entitlement} style={{ width: `${Number(s.percentage)}%` }} className={`flex items-center justify-center truncate px-1 ${i % 2 ? "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100" : "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-100"}`}>{s.label}: {s.percentage}%</div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

function Issues({ plan }: { plan: EntitlementPlan }) {
    if (!plan.issues.length) return null;
    return (
        <div role="alert" className="space-y-1 rounded border border-amber-300 bg-amber-50 p-2 text-xs text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
            <p className="font-semibold">{plan.can_confirm ? "Warnings" : "Confirmation blocked until these are resolved"}</p>
            <ul className="list-disc space-y-0.5 pl-4">
                {plan.issues.map((issue, i) => <li key={`${issue.code}-${i}`}>{issue.blocking && <Badge variant="destructive" className="mr-1 px-1 py-0 text-[10px]">Blocking</Badge>}{issue.message}</li>)}
            </ul>
        </div>
    );
}

function OpeningTable({ plan }: { plan: EntitlementPlan }) {
    const groups = plan.opening.groups;
    return (
        <div className="overflow-x-auto">
            <h3 className="mb-1 text-sm font-semibold tracking-wide">OPENING PLANNING</h3>
            <p className="mb-1 text-xs text-muted-foreground">Total CIF {fmt(plan.opening.total_cif)} · Total quantity {fmt(plan.opening.total_quantity)} · Licence {plan.licence_number}</p>
            <table className="w-full min-w-[720px] border-collapse text-xs">
                <thead><tr className="border-b bg-muted/40 text-left">
                    <th className="px-2 py-1.5">Group</th><th className="px-2 py-1.5">Product / Entitlement</th>
                    <th className={num}>Total Qty</th><th className={num} title="Effective rate; configured maximum shown below when different">Unit Price</th>
                    <th className={num}>Planned CIF</th><th className={num}>CIF Available</th>
                </tr></thead>
                <tbody>
                    {groups.map((g) => {
                        const lines = plan.opening.rows.filter((r) => r.group === g.group);
                        return lines.map((r, i) => (
                            <tr key={`${g.group}-${r.entitlement}`} className="border-b">
                                <td className="px-2 py-1.5 font-medium">{i === 0 ? g.label : ""}</td>
                                <td className="px-2 py-1.5">{r.label}{lines.length > 1 && <span className="ml-1 text-muted-foreground">({r.percentage}%)</span>}</td>
                                <td className={num}>{fmt(r.quantity)}</td>
                                <td className={num}>{fmt(r.unit_price)}{r.unit_price && Number(r.unit_price).toFixed(2) !== Number(r.max_unit_price).toFixed(2) && <span className="block text-[10px] text-muted-foreground">max {fmt(r.max_unit_price)}</span>}</td>
                                <td className={num}>{fmt(r.planned_cif)}</td>
                                <td className={num}>{Number(r.cif_available) === 0 ? "—" : fmt(r.cif_available)}</td>
                            </tr>
                        ));
                    })}
                    <tr className="border-t-2 font-semibold"><td className="px-2 py-1.5" /><td className="px-2 py-1.5">Total</td><td className={num}>{fmt(plan.opening.total_quantity)}</td><td /><td className={num}>{fmt(plan.opening.total_planned_cif)}</td><td className={num}>{Number(plan.opening.unplanned_cif) === 0 ? "" : fmt(plan.opening.unplanned_cif)}</td></tr>
                </tbody>
            </table>
        </div>
    );
}

function AfterTable({ plan }: { plan: EntitlementPlan }) {
    return (
        <div className="overflow-x-auto">
            <h3 className="mb-1 text-sm font-semibold tracking-wide">AFTER BOE DEBITS AND ALLOTTED</h3>
            <table className="w-full min-w-[640px] border-collapse text-xs">
                <thead><tr className="border-b bg-muted/40 text-left"><th className="px-2 py-1.5">Particulars</th><th className={num}>Quantity</th><th className={num}>Rate</th><th className={num}>CIF</th></tr></thead>
                {plan.after.entitlements.map((e) => <EntitlementBlock key={e.entitlement} row={e} />)}
                <tfoot><tr className="border-t-2 font-semibold"><td className="px-2 py-1.5">Total balance CIF</td><td /><td /><td className={num}>{fmt(plan.after.total_balance_cif)}</td></tr></tfoot>
            </table>
        </div>
    );
}

function EntitlementBlock({ row }: { row: EntitlementAfterRow }) {
    const [open, setOpen] = useState<"boe" | "allot" | null>(null);
    const toggle = (key: "boe" | "allot") => setOpen((v) => (v === key ? null : key));
    const products = row.products.length ? ` (${row.products.join(" + ")})` : "";
    return (
        <tbody id={anchorId(row.entitlement)} className="scroll-mt-20">
            <tr className="border-b bg-muted/20"><th colSpan={4} className="px-2 py-1.5 text-left font-semibold">{row.group_label} — {row.label}<span className="font-normal text-muted-foreground">{products}{row.valuation === "RESIDUAL" ? " · absorbs remaining CIF" : ""}</span></th></tr>
            <Line label="Opening" part={row.opening} />
            <Line label="BOE Debited" part={row.boe_debited} count={row.boe_debited.rows.length} expanded={open === "boe"} onToggle={() => toggle("boe")} />
            {open === "boe" && <DetailRows rows={row.boe_debited.rows} />}
            <Line label="Allotted" part={row.allotted} count={row.allotted.rows.length} expanded={open === "allot"} onToggle={() => toggle("allot")} />
            {open === "allot" && <DetailRows rows={row.allotted.rows} />}
            {row.components.map((c) => <tr key={c.code} className="border-b italic text-muted-foreground"><td className="px-2 py-1.5 pl-6">{COMPONENT_LABELS[c.code] ?? c.code}</td><td /><td /><td className={num}>{fmt(c.cif)}</td></tr>)}
            <tr className="border-b font-semibold">
                <td className="px-2 py-1.5">Balance Quantity</td>
                <td className={`${num} ${isNegative(row.balance.quantity) ? "text-destructive" : ""}`}>{fmt(row.balance.quantity)}</td>
                <td className={num}>{fmt(row.balance.rate)}</td>
                <td className={`${num} ${isNegative(row.balance.cif) ? "text-destructive" : ""}`}>{fmt(row.balance.cif)}</td>
            </tr>
        </tbody>
    );
}

function Line({ label, part, count, expanded, onToggle }: { label: string; part: { quantity: string; rate: string | null; cif: string }; count?: number; expanded?: boolean; onToggle?: () => void }) {
    return (
        <tr className="border-b">
            <td className="px-2 py-1.5">
                {onToggle && count ? (
                    <button type="button" className="inline-flex items-center gap-1 hover:underline" aria-expanded={expanded} onClick={onToggle}>
                        {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}{label} <span className="text-muted-foreground">({count})</span>
                    </button>
                ) : label}
            </td>
            <td className={num}>{fmt(part.quantity)}</td><td className={num}>{fmt(part.rate)}</td><td className={num}>{fmt(part.cif)}</td>
        </tr>
    );
}

function DetailRows({ rows }: { rows: DebitRow[] }) {
    return (
        <Fragment>
            {rows.map((r, i) => (
                <tr key={`${r.reference}-${i}`} className="border-b bg-background text-muted-foreground">
                    <td className="px-2 py-1 pl-8">{r.kind === "BOE" ? `BOE ${r.reference}` : `Allotment ${r.reference}`}{typeof r.product === "string" && r.product ? ` · ${r.product}` : ""}{typeof r.item_name === "string" ? ` · ${r.item_name}` : ""}{typeof r.date === "string" ? ` · ${r.date}` : ""}{r.is_frozen ? " · ledger" : ""}</td>
                    <td className={num}>{fmt(r.quantity)}</td><td className={num}>{fmt(r.rate)}</td><td className={num}>{fmt(r.cif)}</td>
                </tr>
            ))}
        </Fragment>
    );
}
