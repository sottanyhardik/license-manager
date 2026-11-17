/** Small, shared presentational pieces for the accounting workspace. */
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { getErrorMessage } from "@/utils/errorUtils";

import { formatMoney, isNegative, type Money } from "./money";

const STATUS_TONE: Record<string, string> = {
    POSTED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    ACCOUNTED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    PAID: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    MATCHED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    RESOLVED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    MIGRATED: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    READY: "bg-sky-50 text-sky-700 ring-sky-600/20",
    CONFIRMED: "bg-sky-50 text-sky-700 ring-sky-600/20",
    PENDING: "bg-sky-50 text-sky-700 ring-sky-600/20",
    PARTIALLY_PAID: "bg-amber-50 text-amber-800 ring-amber-600/20",
    PARTIAL: "bg-amber-50 text-amber-800 ring-amber-600/20",
    PARTIALLY_ACCOUNTED: "bg-amber-50 text-amber-800 ring-amber-600/20",
    NEEDS_REVIEW: "bg-amber-50 text-amber-800 ring-amber-600/20",
    SUSPENSE: "bg-amber-50 text-amber-800 ring-amber-600/20",
    OPEN: "bg-amber-50 text-amber-800 ring-amber-600/20",
    DRAFT: "bg-slate-100 text-slate-700 ring-slate-500/20",
    UNPAID: "bg-slate-100 text-slate-700 ring-slate-500/20",
    UNMATCHED: "bg-slate-100 text-slate-700 ring-slate-500/20",
    NOT_ACCOUNTED: "bg-slate-100 text-slate-700 ring-slate-500/20",
    SKIPPED: "bg-slate-100 text-slate-700 ring-slate-500/20",
    ALREADY_ACCOUNTED: "bg-slate-100 text-slate-700 ring-slate-500/20",
    OVERDUE: "bg-red-50 text-red-700 ring-red-600/20",
    EXCEPTION: "bg-red-50 text-red-700 ring-red-600/20",
    FAILED: "bg-red-50 text-red-700 ring-red-600/20",
    REVERSED: "bg-violet-50 text-violet-700 ring-violet-600/20",
    CANCELLED: "bg-violet-50 text-violet-700 ring-violet-600/20",
};

export function StatusBadge({ status }: { status: string | null | undefined }) {
    if (!status) return <span className="text-slate-400">—</span>;
    const tone = STATUS_TONE[status] ?? "bg-slate-100 text-slate-700 ring-slate-500/20";
    return (
        <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold tracking-wide ring-1 ring-inset ${tone}`}>
            {status.replace(/_/g, " ")}
        </span>
    );
}

export function Amount({ value, blankZero = false, to }: { value: Money | null | undefined; blankZero?: boolean; to?: string }) {
    const text = formatMoney(value, { blankZero });
    const cls = `tabular-nums ${isNegative(value) ? "text-red-700" : ""}`;
    if (to && text) {
        return <Link to={to} className={`${cls} underline decoration-dotted underline-offset-2 hover:text-blue-700`}>{text}</Link>;
    }
    return <span className={cls}>{text}</span>;
}

export interface Column<T> {
    key: string;
    header: ReactNode;
    cell: (row: T) => ReactNode;
    numeric?: boolean;
    className?: string;
}

export function DataGrid<T>({ rows, columns, rowKey, empty = "Nothing to show.", footer, caption }: {
    rows: T[];
    columns: Column<T>[];
    rowKey: (row: T) => string | number;
    empty?: ReactNode;
    footer?: ReactNode;
    caption?: string;
}) {
    return (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
                {caption && <caption className="sr-only">{caption}</caption>}
                <thead className="sticky top-0 bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500">
                    <tr>
                        {columns.map((c) => (
                            <th key={c.key} scope="col"
                                className={`px-3 py-2 font-semibold ${c.numeric ? "text-right" : "text-left"} ${c.className ?? ""}`}>
                                {c.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                    {rows.length === 0 && (
                        <tr><td colSpan={columns.length} className="px-3 py-6 text-center text-slate-500">{empty}</td></tr>
                    )}
                    {rows.map((row) => (
                        <tr key={rowKey(row)} className="hover:bg-blue-50/40 focus-within:bg-blue-50/60">
                            {columns.map((c) => (
                                <td key={c.key} className={`px-3 py-1.5 ${c.numeric ? "text-right tabular-nums" : ""} ${c.className ?? ""}`}>
                                    {c.cell(row)}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
                {footer && <tfoot className="border-t-2 border-slate-300 bg-slate-50 font-semibold">{footer}</tfoot>}
            </table>
        </div>
    );
}

export function Panel({ title, actions, children }: { title: ReactNode; actions?: ReactNode; children: ReactNode }) {
    return (
        <section className="rounded-xl border border-slate-200 bg-white/80 p-4 shadow-sm">
            <header className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
                {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
            </header>
            {children}
        </section>
    );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
    return (
        <label className="flex flex-col gap-1 text-xs font-medium text-slate-600">
            {label}
            {children}
            {hint && <span className="font-normal text-slate-400">{hint}</span>}
        </label>
    );
}

export const inputCls =
    "h-9 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/30";

export function QueryState({ isLoading, error, children, onRetry }: {
    isLoading: boolean; error: unknown; children: ReactNode; onRetry?: () => void;
}) {
    if (isLoading) return <div className="py-8 text-center text-sm text-slate-500" role="status">Loading…</div>;
    if (error) {
        return (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
                <span>{getErrorMessage(error)}</span>
                {onRetry && <button type="button" className="rounded border border-red-300 bg-white px-2 py-0.5 text-xs font-medium hover:bg-red-100" onClick={onRetry}>Retry</button>}
            </div>
        );
    }
    return <>{children}</>;
}

/** Shown instead of an action the user's role cannot perform (the API would refuse it). */
export function ReadOnlyNote({ need }: { need: string }) {
    return <p className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600" role="note">Read-only: this needs {need}.</p>;
}

export function notifyError(error: unknown): void {
    toast.error(getErrorMessage(error));
}

export function NoEntity() {
    return (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <p className="text-sm text-slate-600">No entity books are active yet.</p>
            <Link to="/accounting/setup" className="mt-2 inline-block text-sm font-medium text-blue-700 hover:underline">
                Activate books for a Trade entity →
            </Link>
        </div>
    );
}
