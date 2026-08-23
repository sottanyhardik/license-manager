import { Fragment, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { FinancialLedgerChildRow, FinancialLedgerRow } from "@/pages/license-balance/types";
import { financialLedgerRowClass, fmtDate, fmtInvoiceNumbers, fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";

interface FinancialLedgerTableProps {
    rows: FinancialLedgerRow[];
}

const HEADERS = [
    "Sr", "Date", "Type", "Doc Number", "BOE Number", "BOE Date", "Company", "Item",
    "Invoices", "Qty", "CIF USD", "CIF INR", "Credit", "Debit", "Running Balance", "Remarks",
];

/** One informational child row nested under a "trade" (Licence Trade Sold)
 * parent — always blank Credit/Debit/Running Balance (see
 * `license-balance/types.ts`'s `FinancialLedgerChildRow` docstring). */
function ChildRow({ child }: { child: FinancialLedgerChildRow }) {
    return (
        <tr className="border-t border-border/40 bg-muted/40 text-muted-foreground">
            <td className="px-3 py-1.5" />
            <td className="px-3 py-1.5" />
            <td className="whitespace-nowrap px-3 py-1.5 pl-6 italic">↳ {child.type}</td>
            <td className="px-3 py-1.5" />
            <td className="px-3 py-1.5">{child.boe_number ?? "—"}</td>
            <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(child.boe_date)}</td>
            <td className="px-3 py-1.5">{child.company ?? "—"}</td>
            <td className="px-3 py-1.5">{child.item_name ?? "—"}</td>
            <td className="px-3 py-1.5">{fmtInvoiceNumbers(child.invoice_numbers)}</td>
            <td className="px-3 py-1.5 text-right">{fmtNum(child.qty)}</td>
            <td className="px-3 py-1.5 text-right">{fmtNum(child.cif_usd)}</td>
            <td className="px-3 py-1.5 text-right">{fmtNum(child.cif_inr)}</td>
            <td className="px-3 py-1.5 text-right">—</td>
            <td className="px-3 py-1.5 text-right">—</td>
            <td className="px-3 py-1.5 text-right">—</td>
            <td className="px-3 py-1.5">
                <span className="font-medium">{child.status}</span>
                {child.remarks ? ` — ${child.remarks}` : ""}
            </td>
        </tr>
    );
}

/** Expandable detail row for a "trade" (Sold) row's `mismatch_warning` — a
 * BOE tagged to this invoice whose CIF doesn't cleanly reconcile (or maps
 * to more than one candidate BOE). Never affects `running_balance`; this
 * is a data-quality signal, not a second financial movement — see
 * `license-balance/types.ts`'s `mismatch_warning` docstring. */
function MismatchDetailRow({ warning }: { warning: NonNullable<FinancialLedgerRow["mismatch_warning"]> }) {
    return (
        <tr className="border-t border-border/40 bg-warning/5 text-muted-foreground">
            <td className="px-3 py-1.5" colSpan={2} />
            <td className="whitespace-nowrap px-3 py-1.5 pl-6 italic" colSpan={2}>
                ↳ {warning.status === "ambiguous" ? "Multiple BOEs Linked" : "CIF Mismatch"}
            </td>
            <td className="px-3 py-1.5" colSpan={2}>
                BOE CIF: <span className="font-medium text-foreground">{fmtNum(warning.boe_cif)}</span>
            </td>
            <td className="px-3 py-1.5" colSpan={2}>
                Invoice CIF: <span className="font-medium text-foreground">{fmtNum(warning.invoice_cif)}</span>
            </td>
            <td className="px-3 py-1.5" colSpan={2}>
                Difference: <span className="font-medium text-destructive">{fmtNum(warning.difference)}</span>
            </td>
            <td className="px-3 py-1.5" colSpan={6}>
                Requires manual review via the reconciliation workflow — this figure is not double-counted in the balance.
            </td>
        </tr>
    );
}

/**
 * Overview tab's Financial Ledger table. Hand-rolled `<table>` (not
 * `DataTable.tsx`, which doesn't support this many custom-styled columns) —
 * same approach as `pages/reconciliation/ComparisonTab.tsx`'s row-styling
 * pattern, adapted to a plain table since every row here needs its own
 * semantic color by `row_kind`.
 *
 * "trade" (Licence Trade Sold) rows matched to a real allocation carry a
 * `children` array (one per underlying BOE allocation) — rendered as extra
 * `<tr>`s directly below their parent, expanded by default (mirrors the
 * PDF, which has no interactive collapse) with an optional collapse toggle
 * since this view IS interactive.
 *
 * Relocated (unchanged) from `pages/license-balance/` — still backed by
 * `useLicenseBalanceLedger`.
 */
export default function FinancialLedgerTable({ rows }: FinancialLedgerTableProps) {
    const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

    const toggle = (sr: number) => {
        setCollapsed((prev) => {
            const next = new Set(prev);
            if (next.has(sr)) next.delete(sr);
            else next.add(sr);
            return next;
        });
    };

    return (
        <div className="max-h-[calc(100vh-18rem)] overflow-auto rounded-lg border border-border/70 bg-card">
            <table className="w-full min-w-[1500px] text-[13px]">
                <thead className="sticky top-0 z-[1] bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground backdrop-blur">
                    <tr>
                        {HEADERS.map((h) => (
                            <th key={h} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                                {h}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 && (
                        <tr>
                            <td colSpan={HEADERS.length} className="px-3 py-6 text-center text-muted-foreground">
                                No ledger rows.
                            </td>
                        </tr>
                    )}
                    {rows.map((row) => {
                        const hasChildren = Boolean(row.children && row.children.length > 0);
                        const warning = row.mismatch_warning?.show_warning ? row.mismatch_warning : null;
                        const isExpandable = hasChildren || Boolean(warning);
                        const isCollapsed = collapsed.has(row.sr);
                        return (
                            <Fragment key={row.sr}>
                                <tr className={cn("border-t border-border/60", financialLedgerRowClass(row.row_kind, row.mismatched))}>
                                    <td className="px-3 py-1.5">{row.sr}</td>
                                    <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(row.date)}</td>
                                    <td className="whitespace-nowrap px-3 py-1.5 font-medium">
                                        {isExpandable ? (
                                            <button
                                                type="button"
                                                onClick={() => toggle(row.sr)}
                                                className="inline-flex cursor-pointer items-center gap-1 hover:underline"
                                                aria-label={isCollapsed ? "Expand detail" : "Collapse detail"}
                                            >
                                                {isCollapsed ? (
                                                    <ChevronRight className="size-3.5" />
                                                ) : (
                                                    <ChevronDown className="size-3.5" />
                                                )}
                                                {row.type}
                                            </button>
                                        ) : (
                                            row.type
                                        )}
                                        {row.status && (
                                            <Badge variant="warning" className="ml-2 align-middle">
                                                {row.status}
                                            </Badge>
                                        )}
                                        {warning && (
                                            <Badge variant="destructive" className="ml-2 align-middle gap-1">
                                                <AlertTriangle className="size-3" />
                                                {warning.status === "ambiguous" ? "Multiple BOEs" : "CIF Mismatch"}
                                            </Badge>
                                        )}
                                    </td>
                                    <td className="px-3 py-1.5">{row.document_number ?? "—"}</td>
                                    <td className="px-3 py-1.5" title={row.linked_boe_numbers?.join(", ")}>
                                        {row.boe_number ?? "—"}
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-1.5">
                                        {row.boe_date_display ?? fmtDate(row.boe_date)}
                                    </td>
                                    <td className="px-3 py-1.5">{row.company ?? "—"}</td>
                                    <td className="px-3 py-1.5">{row.item_name ?? "—"}</td>
                                    <td className="px-3 py-1.5">{fmtInvoiceNumbers(row.invoice_numbers)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.qty)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.cif_usd)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.cif_inr)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.credit)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.debit)}</td>
                                    <td className="px-3 py-1.5 text-right font-medium tabular-nums">{fmtNum(row.running_balance)}</td>
                                    <td className="px-3 py-1.5">{row.remarks ?? "—"}</td>
                                </tr>
                                {!isCollapsed && hasChildren &&
                                    row.children!.map((child, idx) => (
                                        <ChildRow key={`${row.sr}-${child.allocation_id ?? idx}`} child={child} />
                                    ))}
                                {!isCollapsed && warning && <MismatchDetailRow key={`${row.sr}-mismatch`} warning={warning} />}
                            </Fragment>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
