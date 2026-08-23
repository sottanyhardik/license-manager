import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
    AlertTriangle, CheckCircle2, Copy, FileText, FileX, IndianRupee, ReceiptText,
} from "lucide-react";

import api from "@/api/axios";
import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";
import DataTable from "@/components/DataTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { formatDate } from "@/utils/dateFormatter";
import { getErrorMessage } from "@/utils/errorUtils";
import { useReconTabQuery } from "./reconciliation/useReconTabQuery";
import {
    fmtList, fmtNum, pick, pickId, reconKeys, type ReconRow,
} from "./reconciliation/reconciliationHelpers";

/**
 * Read-only, portfolio-wide "Issues" page: a lightweight companion to the
 * full BOE / Invoice Reconciliation panel (`ReconciliationPanel.tsx`), whose
 * only job is DISCOVERY — surface which licenses have reconciliation
 * problems and hand off to the (separately built) per-license workspace at
 * `/licenses/:id/balance` to actually fix them. No link/merge/ignore/note
 * actions live here; every tab below is the read-only sibling of the
 * corresponding tab in `ReconciliationPanel.tsx`, reusing the SAME
 * `useReconTabQuery` hook and `reconciliationHelpers` utilities rather than
 * re-deriving field names or fetch logic.
 *
 * Layout choice: TABS (mirroring `ReconciliationPanel.tsx`), not a single
 * unified "one row per license" table. A unified table was considered, but
 * `duplicate-boes`, `cif-comparison`, and `qty-comparison` (see
 * `backend/apps/reconciliation/services/queries.py`'s `duplicate_boes()` /
 * `_linked_trade_comparison()`) return trade/BOE identifiers only — no
 * license number field at all — so a "distinct license number" rollup
 * across all six categories can't be built from these endpoints without
 * inventing data. Tabs let each category show exactly the fields its
 * endpoint actually returns.
 *
 * License linking caveat: none of these detection endpoints return a
 * license `id` (only `license_number` / `license_numbers` strings — see
 * `missing_boe()`, `missing_invoice()`, `duplicate_debits()` in
 * `queries.py`), so a literal `/licenses/<id>/balance` link can't always be
 * constructed. Where a row carries a license number, it links through the
 * existing licenses list filtered by that number (`/licenses?search=...`),
 * the same fallback pattern already used by `Dashboard.tsx` for
 * number-only license references. `licenseHref()` below still checks for a
 * `license_id`/`licence_id` field first, defensively, in case a future
 * backend change adds one — see `reconciliationHelpers.ts`'s `pick()` for
 * the same defensive-accessor convention used throughout this panel.
 */

type IssueTabValue =
    | "missing-boe" | "missing-invoice" | "duplicate-debits" | "duplicate-boes"
    | "cif-comparison" | "qty-comparison";

function licenseHref(row: ReconRow, licenseNumber: string): string {
    const id = pickId(row, "license_id", "licence_id");
    return id !== null ? `/licenses/${id}/balance` : `/licenses?search=${encodeURIComponent(licenseNumber)}`;
}

/** Renders one or more comma-joined license numbers as links, or "—" if none. */
function LicenseLinks({ row, value }: { row: ReconRow; value: unknown }) {
    const raw = value === null || value === undefined ? "" : String(value);
    const numbers = raw.split(",").map(s => s.trim()).filter(Boolean);
    if (numbers.length === 0) return <span className="text-muted-foreground">—</span>;
    return (
        <span className="flex flex-wrap gap-x-1.5 gap-y-0.5">
            {numbers.map((number, idx) => (
                <Link
                    key={`${number}-${idx}`}
                    to={licenseHref(row, number)}
                    className="text-primary underline-offset-2 hover:underline"
                >
                    {number}
                </Link>
            ))}
        </span>
    );
}

function cellText(row: ReconRow, ...keys: string[]): string {
    return String(pick(row, ...keys) ?? "—");
}

function cellDate(row: ReconRow, ...keys: string[]): string {
    const raw = pick(row, ...keys);
    return raw ? (formatDate(String(raw)) || String(raw)) : "—";
}

function IssueTable({
    tabKey, endpoint, columns, cellRender, rowStyle,
}: {
    tabKey: string;
    endpoint: string;
    columns: string[];
    cellRender: Record<string, (item: ReconRow) => ReactNode>;
    rowStyle?: (item: ReconRow) => Record<string, string> | undefined;
}) {
    const { data, isLoading, isError, error } = useReconTabQuery(tabKey, endpoint);

    if (isError) {
        return <p className="p-4 text-sm text-destructive">{getErrorMessage(error)}</p>;
    }

    return (
        <DataTable
            data={data ?? []}
            columns={columns}
            loading={isLoading}
            customCellRender={cellRender}
            getRowStyle={rowStyle}
        />
    );
}

function isNonZeroDifference(row: ReconRow): boolean {
    const diff = Number(pick(row, "difference") ?? 0);
    return !Number.isNaN(diff) && diff !== 0;
}

const DIFF_ROW_STYLE = (row: ReconRow) =>
    isNonZeroDifference(row)
        ? { backgroundColor: "var(--tb-warning-soft)", boxShadow: "inset 3px 0 0 var(--tb-warning)" }
        : undefined;

export default function ReconciliationIssues() {
    const [activeTab, setActiveTab] = useState<IssueTabValue>("missing-boe");

    const { data: summary, isLoading: summaryLoading } = useQuery({
        queryKey: reconKeys.summary,
        queryFn: async () => {
            const { data } = await api.get("reconciliation/summary/");
            return data ?? {};
        },
    });

    const val = (key: string) => (summary ? pick(summary as Record<string, unknown>, key) : null);

    return (
        <>
            <PageHeader
                pretitle="Operations"
                title="Reconciliation Issues"
                description="Portfolio-wide view of licenses with reconciliation problems. Read-only — open a license's Balance workspace to fix any issue."
            />

            <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4">
                <StatCard label="Total BOE" value={val("total_boe") as ReactNode} icon={ReceiptText} tone="primary" loading={summaryLoading} />
                <StatCard label="Total Import Invoices" value={val("total_import_invoices") as ReactNode} icon={FileText} tone="info" loading={summaryLoading} />
                <StatCard label="Matched" value={val("matched") as ReactNode} icon={CheckCircle2} tone="success" loading={summaryLoading} />
                <StatCard label="Unmatched BOE" value={val("unmatched_boe") as ReactNode} icon={AlertTriangle} tone="warning" loading={summaryLoading} onClick={() => setActiveTab("missing-invoice")} />
                <StatCard label="Unmatched Invoice" value={val("unmatched_invoice") as ReactNode} icon={FileX} tone="warning" loading={summaryLoading} onClick={() => setActiveTab("missing-boe")} />
                <StatCard label="Duplicate Debits" value={val("duplicate_debits") as ReactNode} icon={Copy} tone="danger" loading={summaryLoading} onClick={() => setActiveTab("duplicate-debits")} />
                <StatCard label="CIF Difference" value={val("cif_difference") as ReactNode} icon={IndianRupee} tone="danger" loading={summaryLoading} onClick={() => setActiveTab("cif-comparison")} />
            </div>

            <Card className="overflow-hidden border-border/80 shadow-sm shadow-primary/5">
                <CardContent className="p-2 sm:p-3">
                    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as IssueTabValue)}>
                        <div className="overflow-x-auto pb-1">
                        <TabsList className="flex h-9 min-w-max justify-start gap-1" aria-label="Reconciliation issues">
                            <TabsTrigger value="missing-boe">Missing BOE</TabsTrigger>
                            <TabsTrigger value="missing-invoice">Missing Invoice</TabsTrigger>
                            <TabsTrigger value="duplicate-debits">Duplicate Debits</TabsTrigger>
                            <TabsTrigger value="duplicate-boes">Duplicate BOEs</TabsTrigger>
                            <TabsTrigger value="cif-comparison">CIF Comparison</TabsTrigger>
                            <TabsTrigger value="qty-comparison">Quantity Comparison</TabsTrigger>
                        </TabsList>
                        </div>

                        {/* Missing BOE — SALE trade lines with no BOE linked at all. */}
                        <TabsContent value="missing-boe" className="mt-2">
                            <IssueTable
                                tabKey="missing-boe"
                                endpoint="reconciliation/missing-boe/"
                                columns={["invoice_number", "counterparty", "invoice_date", "cif_fc", "qty_kg", "license"]}
                                cellRender={{
                                    invoice_number: (row) => cellText(row, "invoice_number"),
                                    counterparty: (row) => cellText(row, "counterparty"),
                                    invoice_date: (row) => cellDate(row, "invoice_date"),
                                    cif_fc: (row) => fmtNum(pick(row, "cif_fc")),
                                    qty_kg: (row) => fmtNum(pick(row, "qty_kg")),
                                    license: (row) => <LicenseLinks row={row} value={pick(row, "license_number")} />,
                                }}
                            />
                        </TabsContent>

                        {/* Missing Invoice — BOEs with a blank invoice_no. */}
                        <TabsContent value="missing-invoice" className="mt-2">
                            <IssueTable
                                tabKey="missing-invoice"
                                endpoint="reconciliation/missing-invoice/"
                                columns={["bill_of_entry_number", "bill_of_entry_date", "total_cif_fc", "total_quantity", "license"]}
                                cellRender={{
                                    bill_of_entry_number: (row) => cellText(row, "bill_of_entry_number"),
                                    bill_of_entry_date: (row) => cellDate(row, "bill_of_entry_date"),
                                    total_cif_fc: (row) => fmtNum(pick(row, "total_cif_fc")),
                                    total_quantity: (row) => fmtNum(pick(row, "total_quantity")),
                                    license: (row) => <LicenseLinks row={row} value={pick(row, "license_numbers")} />,
                                }}
                            />
                        </TabsContent>

                        {/* Duplicate Debits — a SALE trade-line debit AND a BOE debit row for the same sr_number. */}
                        <TabsContent value="duplicate-debits" className="mt-2">
                            <IssueTable
                                tabKey="duplicate-debits"
                                endpoint="reconciliation/duplicate-debits/"
                                columns={["sr_number_label", "license", "invoice_number", "bill_of_entry_number", "invoice_debit", "boe_debit", "difference"]}
                                rowStyle={DIFF_ROW_STYLE}
                                cellRender={{
                                    sr_number_label: (row) => cellText(row, "sr_number_label", "sr_number_id"),
                                    license: (row) => <LicenseLinks row={row} value={pick(row, "license_number")} />,
                                    invoice_number: (row) => cellText(row, "invoice_number"),
                                    bill_of_entry_number: (row) => cellText(row, "bill_of_entry_number"),
                                    invoice_debit: (row) => fmtNum(pick(row, "invoice_debit")),
                                    boe_debit: (row) => fmtNum(pick(row, "boe_debit")),
                                    difference: (row) => fmtNum(pick(row, "difference")),
                                }}
                            />
                        </TabsContent>

                        {/* Duplicate BOEs — near-duplicate BOE records. No license field on this
                            endpoint (see duplicate_boes() in queries.py), so no license link here. */}
                        <TabsContent value="duplicate-boes" className="mt-2">
                            <IssueTable
                                tabKey="duplicate-boes"
                                endpoint="reconciliation/duplicate-boes/"
                                columns={["bill_of_entry_number_a", "bill_of_entry_number_b", "reason"]}
                                cellRender={{
                                    bill_of_entry_number_a: (row) => cellText(row, "bill_of_entry_number_a"),
                                    bill_of_entry_number_b: (row) => cellText(row, "bill_of_entry_number_b"),
                                    reason: (row) => cellText(row, "reason"),
                                }}
                            />
                        </TabsContent>

                        {/* CIF Comparison — invoice CIF vs linked-BOE debit CIF beyond tolerance.
                            No license field on this endpoint (see _linked_trade_comparison() in
                            queries.py), so no license link here. */}
                        <TabsContent value="cif-comparison" className="mt-2">
                            <IssueTable
                                tabKey="cif-comparison"
                                endpoint="reconciliation/cif-comparison/"
                                columns={["invoice_number", "boe_numbers", "invoice_cif", "boe_cif", "difference"]}
                                rowStyle={DIFF_ROW_STYLE}
                                cellRender={{
                                    invoice_number: (row) => cellText(row, "invoice_number"),
                                    boe_numbers: (row) => fmtList(pick(row, "boe_numbers")),
                                    invoice_cif: (row) => fmtNum(pick(row, "invoice_total")),
                                    boe_cif: (row) => fmtNum(pick(row, "boe_total")),
                                    difference: (row) => fmtNum(pick(row, "difference")),
                                }}
                            />
                        </TabsContent>

                        {/* Quantity Comparison — invoice qty vs linked-BOE debit qty beyond tolerance. */}
                        <TabsContent value="qty-comparison" className="mt-2">
                            <IssueTable
                                tabKey="qty-comparison"
                                endpoint="reconciliation/qty-comparison/"
                                columns={["invoice_number", "boe_numbers", "invoice_qty", "boe_qty", "difference"]}
                                rowStyle={DIFF_ROW_STYLE}
                                cellRender={{
                                    invoice_number: (row) => cellText(row, "invoice_number"),
                                    boe_numbers: (row) => fmtList(pick(row, "boe_numbers")),
                                    invoice_qty: (row) => fmtNum(pick(row, "invoice_total")),
                                    boe_qty: (row) => fmtNum(pick(row, "boe_total")),
                                    difference: (row) => fmtNum(pick(row, "difference")),
                                }}
                            />
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>
        </>
    );
}
