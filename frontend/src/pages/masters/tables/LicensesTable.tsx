/**
 * LicensesTable — premium accordion list for the /licenses route.
 *
 * Design goals (Linear / Stripe / Vercel quality):
 *  • Collapsed row: single scannable line — number, dates, scheme, status, balance
 *  • Expanded: 75 % tab panel + 25 % sticky action panel
 *  • Tabs: Overview · Allocation · Transactions · Documents · History (lazy-loaded)
 *  • Actions always visible — no dropdowns, no modals
 *  • Keyboard-accessible accordion; visible focus states; ARIA compliant
 *  • Responsive: action panel moves below tabs on mobile
 */

import {
    memo,
    useCallback,
    useEffect,
    useState,
} from "react";
import {
    BookCheck,
    Calendar,
    CalendarX,
    ChevronDown,
    CloudDownload,
    Eye,
    FileSpreadsheet,
    FileText,
    Inbox,
    MapPin,
    Network,
    Pencil,
    RefreshCw,
    ScrollText,
    ShieldCheck,
    Target,
    Trash2,
} from "lucide-react";
import { toast } from "sonner";

import api from "../../../api/axios";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { openPdfPreview } from "../../../utils/pdfPreview";
import { openDocument } from "../../../utils/documentDownload";
import { saveFilterState } from "../../../utils/filterPersistence";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface LicenseListItem {
    id: number;
    license_number: string;
    license_date: string | null;
    license_expiry_date: string | null;
    ledger_date: string | null;
    port_name: string | null;
    exporter_name: string | null;
    exporter_iec: string | null;
    get_norm_class: string | null;
    get_balance_cif: string | number | null;
    latest_transfer: string | null;
    purchase_status_label: string | null;
    purchase_status_code: string | null;
    is_manually_planned: boolean;
    has_tl: boolean;
    has_copy: boolean;
    has_condition_sheet: boolean;
    [key: string]: unknown;
}

interface LicenseDetail {
    id: number;
    condition_sheet: string | null;
    import_license: ImportItem[];
    export_license: ExportItem[];
    license_documents: LicenseDoc[];
    [key: string]: unknown;
}

interface ImportItem {
    id: number;
    serial_number: number;
    hs_code_label?: string;
    description: string;
    unit: string;
    quantity: number;
    cif_fc?: number;
    cif_inr?: number;
    alloted_quantity?: number;
    balanced_quantity?: number;
    [key: string]: unknown;
}

interface ExportItem {
    id: number;
    description: string;
    cif_fc?: number;
    fob_inr?: number;
    norm_class_label?: string;
    [key: string]: unknown;
}

interface LicenseDoc {
    id: number;
    type: string;
    file?: string;
    [key: string]: unknown;
}

interface LedgerTransaction {
    date: string | null;
    type: string;
    particular: string;
    invoice_number: string;
    cif_usd: number;
    debit_cif: number;
    credit_cif: number;
    rate: number;
    amount: number;
    debit_amount: number;
    credit_amount: number;
    balance: number;
    profit_loss: number;
    company_name?: string;
    trade_id?: number;
    items?: string;
    sion_norms?: string;
    qty?: number;
}

interface LedgerData {
    license_id: number;
    license_type: string;
    license_number: string;
    license_date: string | null;
    expiry_date: string | null;
    exporter: string;
    port: string;
    total_value: number;
    available_balance: number;
    db_balance: number;
    transactions: LedgerTransaction[];
}

interface Transfer {
    transfer_initiation_date: string | null;
    transfer_acceptance_date: string | null;
    from_iec: string | null;
    from_name: string | null;
    to_iec: string | null;
    to_name: string | null;
    transfer_status: string | null;
}

interface OwnershipData {
    license_number: string;
    last_ownership_fetch: string | null;
    file_transfer_status: string | null;
    current_owner: { iec: string; name: string; address: string | null } | null;
    transfers: Transfer[];
}

export interface LicensesTableProps {
    loading: boolean;
    data: LicenseListItem[];
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: LicenseListItem) => void;
    onViewBalance: (licenseId: number) => void;
    onPlanLicense: (license: { id: number; number: string; balance: number }) => void;
    onViewOwnership: (license: { id: number; number: string }) => void;
    fetchingOwnershipIds: Set<number>;
    onFetchOwnership: (item: LicenseListItem) => void;
    invalidateList: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Pure helpers
// ─────────────────────────────────────────────────────────────────────────────

function fmtInr(val: unknown): string {
    if (val === null || val === undefined || val === "") return "—";
    const n = Number(val);
    if (isNaN(n)) return "—";
    return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}


function parseIndianDate(s: string | null | undefined): Date | null {
    if (!s) return null;
    const p = s.split("-");
    if (p.length !== 3) return null;
    return new Date(Number(p[2]), Number(p[1]) - 1, Number(p[0]));
}

function formatIndianDate(s: string | null | undefined): string {
    if (!s) return "—";
    const d = parseIndianDate(s);
    if (!d) return s;
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Derive a display status from expiry + balance */
function deriveStatus(item: LicenseListItem): {
    label: string;
    dot: string;
    badge: string;
} {
    const isExpired = !!(
        item.license_expiry_date &&
        parseIndianDate(item.license_expiry_date)! < new Date()
    );
    const balance = Number(item.get_balance_cif ?? 0);

    if (isExpired) {
        return {
            label: "Expired",
            dot: "bg-destructive",
            badge: "bg-destructive/10 text-destructive ring-1 ring-destructive/20",
        };
    }
    if (balance <= 0) {
        return {
            label: "Exhausted",
            dot: "bg-muted-foreground/60",
            badge: "bg-muted text-muted-foreground ring-1 ring-border",
        };
    }
    if (item.is_manually_planned) {
        return {
            label: "Planned",
            dot: "bg-emerald-500",
            badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
        };
    }
    return {
        label: "Active",
        dot: "bg-emerald-500",
        badge: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
    };
}

function borderAccentCls(item: LicenseListItem): string {
    const isExpired = !!(
        item.license_expiry_date &&
        parseIndianDate(item.license_expiry_date)! < new Date()
    );
    if (isExpired) return "border-l-destructive";
    if (item.is_manually_planned) return "border-l-emerald-500";
    return "border-l-primary";
}

// ─────────────────────────────────────────────────────────────────────────────
// Action Panel
// ─────────────────────────────────────────────────────────────────────────────

interface ActionPanelProps {
    item: LicenseListItem;
    canWrite: boolean;
    isFetchingDGFT: boolean;
    onEdit: () => void;
    onViewBalance: () => void;
    onPlanLicense: () => void;
    onViewOwnership: () => void;
    onDownloadPdf: () => void;
    onDownloadExcel: () => void;
    onFetchDGFT: () => void;
    onDelete: () => void;
}

function ActionPanel({
    item,
    canWrite,
    isFetchingDGFT,
    onEdit,
    onViewBalance,
    onPlanLicense,
    onViewOwnership,
    onDownloadPdf,
    onDownloadExcel,
    onFetchDGFT,
    onDelete,
}: ActionPanelProps) {
    return (
        <aside
            aria-label={`Actions for license ${item.license_number}`}
            className="w-full shrink-0 border-t border-border/50 bg-muted/20 px-4 py-4 lg:w-60 lg:border-l lg:border-t-0"
        >
            {/* Primary action */}
            {canWrite && (
                <Button
                    onClick={onPlanLicense}
                    className="mb-3 w-full justify-start gap-2.5"
                    size="sm"
                >
                    <Target className="size-4 shrink-0" aria-hidden="true" />
                    Plan Utilization
                </Button>
            )}

            {/* Secondary actions */}
            <div className="flex flex-col gap-0.5">
                <ActionRow icon={Network} label="View Ownership" onClick={onViewOwnership} />
                <ActionRow icon={Eye} label="View Balance" onClick={onViewBalance} />

                <Separator className="my-2" />

                <ActionRow icon={FileText} label="Balance PDF" onClick={onDownloadPdf} />
                <ActionRow icon={FileSpreadsheet} label="Balance Excel" onClick={onDownloadExcel} />

                {canWrite && (
                    <>
                        <Separator className="my-2" />
                        <ActionRow
                            icon={isFetchingDGFT ? RefreshCw : CloudDownload}
                            label={isFetchingDGFT ? "Fetching…" : "Fetch from DGFT"}
                            onClick={onFetchDGFT}
                            disabled={isFetchingDGFT}
                            spinning={isFetchingDGFT}
                        />
                    </>
                )}

                {canWrite && (
                    <>
                        <Separator className="my-2" />
                        <button
                            type="button"
                            onClick={onDelete}
                            className="flex w-full cursor-pointer items-center gap-2.5 rounded-lg border border-destructive/30 px-3 py-2 text-[13px] font-medium text-destructive transition-colors hover:bg-destructive/5"
                        >
                            <Trash2 className="size-4 shrink-0" aria-hidden="true" />
                            Delete
                        </button>
                    </>
                )}
            </div>

            {/* Bottom quick actions */}
            <div className="mt-3 flex gap-2">
                {canWrite && (
                    <Button variant="outline" size="sm" onClick={onEdit} className="flex-1 gap-1.5">
                        <Pencil className="size-3.5" aria-hidden="true" />
                        Edit
                    </Button>
                )}
                <Button variant="outline" size="sm" onClick={onViewBalance} className="flex-1 gap-1.5">
                    <Eye className="size-3.5" aria-hidden="true" />
                    Balance
                </Button>
            </div>
        </aside>
    );
}

function ActionRow({
    icon: Icon,
    label,
    onClick,
    disabled = false,
    spinning = false,
}: {
    icon: React.ElementType;
    label: string;
    onClick: () => void;
    disabled?: boolean;
    spinning?: boolean;
}) {
    return (
        <button
            type="button"
            onClick={onClick}
            disabled={disabled}
            className="flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-foreground/80 transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
            <Icon className={cn("size-4 shrink-0", spinning && "animate-spin")} aria-hidden="true" />
            {label}
        </button>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Tab content components (all lazy)
// ─────────────────────────────────────────────────────────────────────────────

function OverviewTab({ item, detail }: { item: LicenseListItem; detail: LicenseDetail | null }) {
    const fields: { label: string; value: string }[] = [
        { label: "Port", value: item.port_name || "—" },
        { label: "Scheme", value: item.purchase_status_label || "—" },
        { label: "Norm Class", value: item.get_norm_class || "—" },
        { label: "Created On", value: formatIndianDate(item.license_date) },
        { label: "Valid Until", value: formatIndianDate(item.license_expiry_date) },
        { label: "Ledger Date", value: formatIndianDate(item.ledger_date) },
        { label: "Transfer Status", value: item.latest_transfer || "—" },
        { label: "Exporter", value: item.exporter_name || "—" },
        { label: "IEC", value: item.exporter_iec || "—" },
    ];

    const notes = detail?.condition_sheet;

    return (
        <div className="px-1 py-4">
            {/* Field grid */}
            <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3">
                {fields.map((f) => (
                    <div key={f.label}>
                        <dt className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                            {f.label}
                        </dt>
                        <dd className="mt-0.5 truncate text-sm font-medium text-foreground" title={f.value}>
                            {f.value}
                        </dd>
                    </div>
                ))}
            </dl>

            {/* Notes */}
            <div className="mt-6">
                <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    <ScrollText className="size-3.5" aria-hidden="true" />
                    Notes
                </div>
                {detail === null ? (
                    <div className="space-y-1.5">
                        <Skeleton className="h-3 w-3/4" />
                        <Skeleton className="h-3 w-1/2" />
                    </div>
                ) : notes ? (
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/80">{notes}</p>
                ) : (
                    <p className="text-sm text-muted-foreground">No notes available.</p>
                )}
            </div>
        </div>
    );
}

function AllocationTab({ item: _item, detail, loading }: { item: LicenseListItem; detail: LicenseDetail | null; loading: boolean }) {
    if (loading) return <TabSkeleton />;
    const rows = detail?.import_license ?? [];

    if (rows.length === 0) {
        return (
            <EmptyTabState
                icon={ShieldCheck}
                title="No import items"
                description="This license has no import line items."
            />
        );
    }

    return (
        <div className="overflow-x-auto py-4">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-border/60 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <th scope="col" className="pb-2 pr-4">Sl#</th>
                        <th scope="col" className="pb-2 pr-4">HS Code</th>
                        <th scope="col" className="pb-2 pr-4">Description</th>
                        <th scope="col" className="pb-2 pr-4 text-right">Qty</th>
                        <th scope="col" className="pb-2 pr-4 text-right">Allotted</th>
                        <th scope="col" className="pb-2 text-right">Balance</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                    {rows.map((r) => {
                        const bal = (r.balanced_quantity ?? 0);
                        const balCls = bal > 0 ? "text-emerald-700 font-semibold" : "text-muted-foreground";
                        return (
                            <tr key={r.id} className="hover:bg-muted/30 transition-colors">
                                <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{r.serial_number}</td>
                                <td className="py-2 pr-4 font-mono text-xs">{r.hs_code_label || "—"}</td>
                                <td className="max-w-[200px] py-2 pr-4">
                                    <span className="line-clamp-2 text-xs leading-relaxed" title={r.description}>
                                        {r.description || "—"}
                                    </span>
                                </td>
                                <td className="py-2 pr-4 text-right tabular-nums">{r.quantity?.toFixed(3) ?? "—"}</td>
                                <td className="py-2 pr-4 text-right tabular-nums">{(r.alloted_quantity ?? 0).toFixed ? Number(r.alloted_quantity ?? 0).toFixed(3) : "—"}</td>
                                <td className={cn("py-2 text-right tabular-nums", balCls)}>{Number(bal).toFixed(3)}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function TransactionsTab({
    item: _item,
    ledger,
    loading,
}: {
    item: LicenseListItem;
    ledger: LedgerData | null;
    loading: boolean;
}) {
    if (loading) return <TabSkeleton />;
    if (!ledger) return <TabSkeleton />;

    const txns = ledger.transactions ?? [];

    if (txns.length === 0) {
        return (
            <EmptyTabState
                icon={ScrollText}
                title="No transactions"
                description="No ledger entries found for this license."
            />
        );
    }

    function typeBadge(type: string) {
        const t = (type || "").toUpperCase();
        if (t === "OPENING") return "bg-blue-50 text-blue-700 ring-1 ring-blue-200";
        if (t.includes("PURCHASE") || t.includes("COMMISSION")) return "bg-amber-50 text-amber-700 ring-1 ring-amber-200";
        if (t === "SALE") return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
        return "bg-muted text-muted-foreground ring-1 ring-border";
    }

    const fmtNum = (v: number | undefined | null, dp = 2) => {
        if (!v && v !== 0) return "—";
        return Number(v).toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp });
    };

    return (
        <div className="py-3">
            {/* Summary bar */}
            <div className="mb-3 flex flex-wrap gap-4 rounded-lg bg-muted/30 px-4 py-2.5 text-sm">
                <div>
                    <span className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Total Value</span>
                    <div className="font-semibold tabular-nums">${fmtNum(ledger.total_value)}</div>
                </div>
                <div>
                    <span className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Available Balance</span>
                    <div className="font-semibold tabular-nums text-primary">${fmtNum(ledger.available_balance)}</div>
                </div>
                <div>
                    <span className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Transactions</span>
                    <div className="font-semibold tabular-nums">{txns.length}</div>
                </div>
            </div>

            {/* Ledger table */}
            <div className="overflow-x-auto rounded-lg border border-border/50">
                <table className="w-full text-sm">
                    <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur-sm">
                        <tr className="border-b border-border text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                            <th scope="col" className="px-3 py-2.5">Date</th>
                            <th scope="col" className="px-3 py-2.5">Type</th>
                            <th scope="col" className="px-3 py-2.5">Particular</th>
                            <th scope="col" className="px-3 py-2.5">Reference</th>
                            <th scope="col" className="px-3 py-2.5 text-right">Debit (CIF $)</th>
                            <th scope="col" className="px-3 py-2.5 text-right">Credit (CIF $)</th>
                            <th scope="col" className="px-3 py-2.5 text-right">Balance (CIF $)</th>
                            <th scope="col" className="hidden px-3 py-2.5 text-right lg:table-cell">P/L (&#8377;)</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                        {txns.map((txn, idx) => {
                            const isDebit = txn.debit_cif > 0;
                            const isCredit = txn.credit_cif > 0;
                            return (
                                <tr key={`${txn.trade_id ?? idx}`} className="transition-colors hover:bg-muted/20">
                                    <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                                        {txn.date ? String(txn.date) : "—"}
                                    </td>
                                    <td className="px-3 py-2">
                                        <span className={cn("rounded-full px-2 py-0.5 text-[10.5px] font-semibold", typeBadge(txn.type))}>
                                            {txn.type}
                                        </span>
                                    </td>
                                    <td className="max-w-[200px] px-3 py-2">
                                        <div className="truncate text-xs" title={txn.particular}>{txn.particular || "—"}</div>
                                        {txn.items && <div className="truncate text-[10.5px] text-muted-foreground" title={txn.items}>{txn.items}</div>}
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted-foreground">
                                        {txn.invoice_number || "—"}
                                    </td>
                                    <td className="px-3 py-2 text-right tabular-nums text-xs">
                                        {isDebit ? <span className="font-medium text-amber-700">{fmtNum(txn.debit_cif)}</span> : <span className="text-muted-foreground/40">—</span>}
                                    </td>
                                    <td className="px-3 py-2 text-right tabular-nums text-xs">
                                        {isCredit ? <span className="font-medium text-emerald-700">{fmtNum(txn.credit_cif)}</span> : <span className="text-muted-foreground/40">—</span>}
                                    </td>
                                    <td className="px-3 py-2 text-right tabular-nums text-xs font-semibold text-foreground">
                                        {fmtNum(txn.balance)}
                                    </td>
                                    <td className="hidden px-3 py-2 text-right tabular-nums text-xs lg:table-cell">
                                        {txn.profit_loss !== 0 ? (
                                            <span className={txn.profit_loss > 0 ? "text-emerald-700" : "text-destructive"}>
                                                {txn.profit_loss > 0 ? "+" : ""}{fmtNum(txn.profit_loss, 0)}
                                            </span>
                                        ) : <span className="text-muted-foreground/40">—</span>}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function DocumentsTab({ item: _item, detail, loading }: { item: LicenseListItem; detail: LicenseDetail | null; loading: boolean }) {
    if (loading) return <TabSkeleton />;

    const docs = detail?.license_documents ?? [];

    const typeBadgeCls = (type: string) => {
        const t = (type || "").toUpperCase();
        if (t === "LICENSE COPY") return "bg-blue-50 text-blue-700 ring-1 ring-blue-200";
        if (t === "TRANSFER LETTER") return "bg-violet-50 text-violet-700 ring-1 ring-violet-200";
        return "bg-muted text-muted-foreground ring-1 ring-border";
    };

    const getFileName = (file: string | undefined) => {
        if (!file) return "document";
        try {
            return decodeURIComponent(String(file).split("?")[0].split("/").pop() || "document");
        } catch {
            return "document";
        }
    };

    if (docs.length === 0) {
        return (
            <EmptyTabState
                icon={FileText}
                title="No documents"
                description="No documents have been uploaded for this license."
            />
        );
    }

    return (
        <div className="py-3">
            <div className="overflow-hidden rounded-lg border border-border/50">
                <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                        <tr className="border-b border-border text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                            <th scope="col" className="px-4 py-2.5">Type</th>
                            <th scope="col" className="px-4 py-2.5">File Name</th>
                            <th scope="col" className="px-4 py-2.5 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border/40">
                        {docs.map((doc) => {
                            const fileName = getFileName(doc.file as string | undefined);
                            return (
                                <tr key={doc.id} className="transition-colors hover:bg-muted/20">
                                    <td className="px-4 py-3">
                                        <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-semibold", typeBadgeCls(doc.type as string))}>
                                            {doc.type as string || "OTHER"}
                                        </span>
                                    </td>
                                    <td className="max-w-[300px] px-4 py-3">
                                        <div className="flex items-center gap-2">
                                            <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                            <span className="truncate text-xs text-foreground" title={fileName}>{fileName}</span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        {doc.file && (
                                            <button
                                                type="button"
                                                onClick={() => openDocument(doc.file as string)}
                                                className="text-xs font-medium text-primary hover:underline focus-visible:underline focus-visible:outline-none"
                                            >
                                                View
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function HistoryTab({
    item: _item,
    ownershipData,
    loading,
}: {
    item: LicenseListItem;
    ownershipData: OwnershipData | null;
    loading: boolean;
}) {
    if (loading) return <TabSkeleton />;

    if (!ownershipData) {
        return (
            <EmptyTabState
                icon={Network}
                title="No ownership data"
                description="Click 'Fetch from DGFT' in the action panel to load ownership history."
            />
        );
    }

    const transfers = ownershipData.transfers ?? [];

    function statusConfig(status: string | null) {
        const s = (status || "").toUpperCase();
        if (s.includes("COMPLETE") || s.includes("TRANSFER")) return { dot: "bg-emerald-500", badge: "bg-emerald-50 text-emerald-700" };
        if (s.includes("PENDING") || s.includes("PROCESSING") || s.includes("INITIAT")) return { dot: "bg-amber-400", badge: "bg-amber-50 text-amber-700" };
        if (s.includes("REJECT") || s.includes("CANCEL")) return { dot: "bg-destructive", badge: "bg-destructive/10 text-destructive" };
        return { dot: "bg-muted-foreground/40", badge: "bg-muted text-muted-foreground" };
    }

    return (
        <div className="py-3">
            {/* Current owner card */}
            {ownershipData.current_owner && (
                <div className="mb-4 rounded-lg border border-border/50 bg-card px-4 py-3">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Current Owner</div>
                    <div className="mt-1 font-semibold text-foreground">{ownershipData.current_owner.name}</div>
                    <div className="text-xs text-muted-foreground">IEC: {ownershipData.current_owner.iec}</div>
                    {ownershipData.current_owner.address && (
                        <div className="mt-0.5 text-xs text-muted-foreground">{ownershipData.current_owner.address}</div>
                    )}
                    {ownershipData.last_ownership_fetch && (
                        <div className="mt-2 text-[10.5px] text-muted-foreground">
                            Last synced: {new Date(ownershipData.last_ownership_fetch).toLocaleString("en-IN")}
                        </div>
                    )}
                </div>
            )}

            {/* File transfer status */}
            {ownershipData.file_transfer_status && (
                <div className="mb-4 rounded-lg border border-border/50 bg-muted/30 px-4 py-2.5">
                    <span className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">File Transfer Status: </span>
                    <span className="text-sm font-medium text-foreground">{ownershipData.file_transfer_status}</span>
                </div>
            )}

            {/* Vertical timeline of transfers */}
            {transfers.length === 0 ? (
                <EmptyTabState
                    icon={Network}
                    title="No transfer history"
                    description="No ownership transfers recorded for this license."
                />
            ) : (
                <div className="relative pl-6">
                    {/* Vertical line */}
                    <div className="absolute bottom-0 left-2 top-0 w-px bg-border" aria-hidden="true" />

                    {transfers.map((t, idx) => {
                        const sc = statusConfig(t.transfer_status);
                        const date = t.transfer_acceptance_date || t.transfer_initiation_date;
                        const formattedDate = date
                            ? new Date(date).toLocaleDateString("en-IN", {
                                day: "numeric", month: "short", year: "numeric",
                            })
                            : null;

                        return (
                            <div key={idx} className="relative mb-5 last:mb-0">
                                {/* Dot */}
                                <div className={cn("absolute -left-[22px] top-1.5 size-3 rounded-full ring-2 ring-background", sc.dot)} aria-hidden="true" />

                                <div className="rounded-lg border border-border/50 bg-card px-4 py-3">
                                    {/* Header */}
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <span className={cn("rounded-full px-2.5 py-0.5 text-[11px] font-semibold", sc.badge)}>
                                            {t.transfer_status || "Unknown"}
                                        </span>
                                        {formattedDate && (
                                            <span className="text-xs text-muted-foreground">{formattedDate}</span>
                                        )}
                                    </div>

                                    {/* From ↔ To */}
                                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                                        <div>
                                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">From</div>
                                            <div className="font-medium text-foreground">{t.from_name || "—"}</div>
                                            {t.from_iec && <div className="text-xs text-muted-foreground">IEC: {t.from_iec}</div>}
                                        </div>
                                        <Network className="mx-2 size-4 shrink-0 text-muted-foreground/50" aria-hidden="true" />
                                        <div>
                                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">To</div>
                                            <div className="font-medium text-foreground">{t.to_name || "—"}</div>
                                            {t.to_iec && <div className="text-xs text-muted-foreground">IEC: {t.to_iec}</div>}
                                        </div>
                                    </div>

                                    {/* Dates */}
                                    {t.transfer_initiation_date && (
                                        <div className="mt-1.5 text-[10.5px] text-muted-foreground">
                                            Initiated: {new Date(t.transfer_initiation_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared UI sub-components
// ─────────────────────────────────────────────────────────────────────────────

function TabSkeleton() {
    return (
        <div className="space-y-3 py-4">
            {[1, 2, 3].map((i) => (
                <div key={i} className="flex gap-3">
                    <Skeleton className="h-4 w-1/4" />
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-4 w-1/4" />
                </div>
            ))}
        </div>
    );
}

function EmptyTabState({
    icon: Icon,
    title,
    description,
}: {
    icon: React.ElementType;
    title: string;
    description: string;
}) {
    return (
        <div className="flex flex-col items-center py-10 text-center">
            <div className="mb-3 flex size-10 items-center justify-center rounded-full bg-muted">
                <Icon className="size-5 text-muted-foreground/60" aria-hidden="true" />
            </div>
            <div className="text-sm font-medium text-muted-foreground">{title}</div>
            <div className="mt-1 text-xs text-muted-foreground/70">{description}</div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Single license accordion row
// ─────────────────────────────────────────────────────────────────────────────

type TabId = "overview" | "allocation" | "transactions" | "documents" | "history";

const TABS: { id: TabId; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "allocation", label: "Allocation" },
    { id: "transactions", label: "Transactions" },
    { id: "documents", label: "Documents" },
    { id: "history", label: "History" },
];

interface LicenseRowProps {
    item: LicenseListItem;
    expanded: boolean;
    onToggle: () => void;
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: LicenseListItem) => void;
    onViewBalance: (id: number) => void;
    onPlanLicense: (lic: { id: number; number: string; balance: number }) => void;
    onViewOwnership: (lic: { id: number; number: string }) => void;
    isFetchingDGFT: boolean;
    onFetchDGFT: (item: LicenseListItem) => void;
}

const LicenseRow = memo(function LicenseRow({
    item,
    expanded,
    onToggle,
    canWrite,
    entityName,
    filterParams,
    currentPage,
    pageSize,
    navigate,
    onDelete,
    onViewBalance,
    onPlanLicense,
    onViewOwnership,
    isFetchingDGFT,
    onFetchDGFT,
}: LicenseRowProps) {
    const [activeTab, setActiveTab] = useState<TabId>("overview");
    const [visited, setVisited] = useState<Set<TabId>>(new Set(["overview"]));
    const [detail, setDetail] = useState<LicenseDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [ledger, setLedger] = useState<LedgerData | null>(null);
    const [ledgerLoading, setLedgerLoading] = useState(false);
    const [ownershipData, setOwnershipData] = useState<OwnershipData | null>(null);
    const [ownershipLoading, setOwnershipLoading] = useState(false);

    const isExpired = !!(
        item.license_expiry_date && parseIndianDate(item.license_expiry_date)! < new Date()
    );
    const status = deriveStatus(item);

    // Fetch detail when first expanded
    useEffect(() => {
        if (!expanded || detail !== null || detailLoading) return;
        let cancelled = false;
        setDetailLoading(true);
        api.get(`licenses/${item.id}/`)
            .then(({ data }) => {
                if (!cancelled) setDetail(data);
            })
            .catch(() => {
                if (!cancelled) toast.error("Failed to load license details");
            })
            .finally(() => {
                if (!cancelled) setDetailLoading(false);
            });
        return () => { cancelled = true; };
    }, [expanded, item.id, detail, detailLoading]);

    const handleTabChange = useCallback((tab: string) => {
        const t = tab as TabId;
        setActiveTab(t);
        setVisited((prev) => new Set([...prev, t]));
        // Lazy-fetch ledger on first visit to transactions tab
        if (t === "transactions" && !ledger && !ledgerLoading) {
            setLedgerLoading(true);
            api.get(`license-ledger/${item.id}/ledger_detail/`)
                .then(({ data }) => setLedger(data))
                .catch(() => toast.error("Failed to load ledger"))
                .finally(() => setLedgerLoading(false));
        }
        // Lazy-fetch ownership on first visit to history tab
        if (t === "history" && !ownershipData && !ownershipLoading) {
            setOwnershipLoading(true);
            api.get(`license-actions/${item.id}/ownership-data/`)
                .then(({ data }) => setOwnershipData(data))
                .catch(() => toast.error("Failed to load ownership data"))
                .finally(() => setOwnershipLoading(false));
        }
    }, [item.id, ledger, ledgerLoading, ownershipData, ownershipLoading]);

    const handleOpenMergedPdf = useCallback(async (e: React.MouseEvent) => {
        e.stopPropagation(); // prevent accordion toggle
        if (!item.has_tl && !item.has_copy) return;
        try {
            const r = await api.get(`licenses/${item.id}/merged-documents/`, {
                responseType: "blob",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            openPdfPreview(r.data as Blob, `${item.license_number || item.id}-documents.pdf`);
        } catch (err: unknown) {
            const status = (err as { response?: { status?: number } })?.response?.status;
            if (status === 404) {
                toast.warning("Document files are not available on this server.");
            } else {
                toast.error("Failed to load license documents");
            }
        }
    }, [item.id, item.license_number, item.has_tl, item.has_copy]);

    const navigateToEdit = useCallback(() => {
        saveFilterState(entityName, {
            filters: filterParams,
            pagination: { currentPage, pageSize },
            search: "",
        });
        navigate(`/licenses/${item.id}/edit`);
    }, [entityName, filterParams, currentPage, pageSize, navigate, item.id]);

    const handleDownloadPdf = useCallback(async () => {
        try {
            const r = await api.get(`licenses/${item.id}/balance-pdf/`, {
                responseType: "blob",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            openPdfPreview(r.data as Blob, `${item.license_number || item.id}-balance.pdf`);
        } catch (err: unknown) {
            toast.error((err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Failed to generate PDF");
        }
    }, [item.id, item.license_number]);

    const handleDownloadExcel = useCallback(async () => {
        try {
            const r = await api.get(`licenses/${item.id}/balance-excel/`, {
                responseType: "blob",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            const blob = new Blob([r.data as Blob], {
                type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${item.license_number || item.id}-balance.xlsx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => window.URL.revokeObjectURL(url), 10_000);
        } catch (err: unknown) {
            toast.error((err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Failed to generate Excel");
        }
    }, [item.id, item.license_number]);

    return (
        <article
            aria-label={`License ${item.license_number || item.id}`}
            className={cn(
                "overflow-hidden rounded-2xl border border-l-[3px] bg-card shadow-sm transition-shadow",
                expanded ? "shadow-md" : "hover:shadow-md",
                borderAccentCls(item)
            )}
        >
            {/* ── Collapsed / always-visible header ─────────────────── */}
            <button
                type="button"
                onClick={onToggle}
                aria-expanded={expanded}
                aria-controls={`license-content-${item.id}`}
                className="group w-full cursor-pointer text-left"
            >
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-5 py-3.5">
                    {/* License number — primary visual anchor; click opens merged PDF */}
                    <button
                        type="button"
                        onClick={handleOpenMergedPdf}
                        onKeyDown={(e) => e.key === "Enter" && handleOpenMergedPdf(e as unknown as React.MouseEvent)}
                        aria-label={`View documents for license ${item.license_number}`}
                        className={cn(
                            "font-mono text-[17px] font-bold tracking-tight",
                            "underline-offset-2 focus-visible:outline-none focus-visible:ring-0",
                            (item.has_tl || item.has_copy)
                                ? "cursor-pointer text-primary hover:underline focus-visible:underline"
                                : "cursor-default text-foreground"
                        )}
                    >
                        {item.license_number || "—"}
                    </button>

                    {/* Dates row */}
                    <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        {item.license_date && (
                            <span className="flex items-center gap-1">
                                <Calendar className="size-3" aria-hidden="true" />
                                {item.license_date}
                            </span>
                        )}
                        {item.license_expiry_date && (
                            <span className={cn("flex items-center gap-1", isExpired && "text-destructive")}>
                                <CalendarX className="size-3" aria-hidden="true" />
                                Exp: {item.license_expiry_date}
                            </span>
                        )}
                        {item.ledger_date && (
                            <span className="flex items-center gap-1 font-medium text-emerald-700">
                                <BookCheck className="size-3" aria-hidden="true" />
                                Ledger: {item.ledger_date}
                            </span>
                        )}
                        {item.port_name && (
                            <span className="flex items-center gap-1">
                                <MapPin className="size-3" aria-hidden="true" />
                                {item.port_name}
                            </span>
                        )}
                    </span>

                    {/* Scheme label */}
                    {item.purchase_status_label && (
                        <span className="text-xs text-muted-foreground">{item.purchase_status_label}</span>
                    )}

                    {/* Spacer */}
                    <span className="flex-1" />

                    {/* Status badge */}
                    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold", status.badge)}>
                        <span className={cn("size-1.5 rounded-full", status.dot)} aria-hidden="true" />
                        {status.label}
                    </span>

                    {/* Balance — collapsed only */}
                    {!expanded && (
                        <span className="text-sm font-bold tabular-nums text-foreground">
                            Balance CIF <span className="ml-1">{fmtInr(item.get_balance_cif)}</span>
                        </span>
                    )}

                    {/* Chevron */}
                    <ChevronDown
                        className={cn(
                            "size-4 shrink-0 text-muted-foreground/60 transition-transform duration-200",
                            expanded && "rotate-180"
                        )}
                        aria-hidden="true"
                    />
                </div>
            </button>

            {/* ── Expanded content ───────────────────────────────────── */}
            {expanded && (
                <div id={`license-content-${item.id}`}>
                    {/* Info strip */}
                    <div className="grid grid-cols-2 gap-4 border-y border-border/50 bg-muted/30 px-5 py-3 sm:grid-cols-4 lg:grid-cols-5">
                        <InfoField label="Norm Class" value={item.get_norm_class} mono />
                        <InfoField label="Exporter" value={item.exporter_name} />
                        <InfoField label="IEC" value={item.exporter_iec} mono />
                        <InfoField label="Transfer Status" value={item.latest_transfer} />
                        <div className="col-span-2 sm:col-span-4 lg:col-span-1">
                            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                                Balance CIF
                            </div>
                            <div className="mt-0.5 text-[22px] font-bold tabular-nums leading-none text-foreground">
                                {fmtInr(item.get_balance_cif)}
                            </div>
                        </div>
                    </div>

                    {/* Main content + action panel */}
                    <div className="flex flex-col lg:flex-row">
                        {/* Left: Tabs (75%) */}
                        <div className="min-w-0 flex-1 px-5 pb-5">
                            <div>
                                {/* Custom underline-style tab list */}
                                <div className="mb-4 border-b border-border/50">
                                    <div
                                        role="tablist"
                                        aria-label={`License ${item.license_number} sections`}
                                        className="-mb-px flex gap-0 overflow-x-auto"
                                    >
                                        {TABS.map((tab) => (
                                            <button
                                                key={tab.id}
                                                role="tab"
                                                aria-selected={activeTab === tab.id}
                                                aria-controls={`tabpanel-${item.id}-${tab.id}`}
                                                type="button"
                                                onClick={() => handleTabChange(tab.id)}
                                                className={cn(
                                                    "shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                                                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
                                                    activeTab === tab.id
                                                        ? "border-primary text-primary"
                                                        : "border-transparent text-muted-foreground hover:text-foreground"
                                                )}
                                            >
                                                {tab.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Tab panels */}
                                {TABS.map((tab) => (
                                    <div
                                        key={tab.id}
                                        id={`tabpanel-${item.id}-${tab.id}`}
                                        role="tabpanel"
                                        aria-labelledby={`tab-${item.id}-${tab.id}`}
                                        hidden={activeTab !== tab.id}
                                        className="min-h-[180px]"
                                    >
                                        {visited.has(tab.id) && (
                                            <>
                                                {tab.id === "overview" && (
                                                    <OverviewTab item={item} detail={detail} />
                                                )}
                                                {tab.id === "allocation" && (
                                                    <AllocationTab item={item} detail={detail} loading={detailLoading} />
                                                )}
                                                {tab.id === "transactions" && (
                                                    <TransactionsTab item={item} ledger={ledger} loading={ledgerLoading} />
                                                )}
                                                {tab.id === "documents" && (
                                                    <DocumentsTab item={item} detail={detail} loading={detailLoading} />
                                                )}
                                                {tab.id === "history" && (
                                                    <HistoryTab item={item} ownershipData={ownershipData} loading={ownershipLoading} />
                                                )}
                                            </>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Right: Action panel (25%) */}
                        <ActionPanel
                            item={item}
                            canWrite={canWrite}
                            isFetchingDGFT={isFetchingDGFT}
                            onEdit={navigateToEdit}
                            onViewBalance={() => onViewBalance(item.id)}
                            onPlanLicense={() =>
                                onPlanLicense({
                                    id: item.id,
                                    number: item.license_number,
                                    balance: Number(item.get_balance_cif || 0),
                                })
                            }
                            onViewOwnership={() =>
                                onViewOwnership({ id: item.id, number: item.license_number })
                            }
                            onDownloadPdf={handleDownloadPdf}
                            onDownloadExcel={handleDownloadExcel}
                            onFetchDGFT={() => onFetchDGFT(item)}
                            onDelete={() => onDelete(item)}
                        />
                    </div>
                </div>
            )}
        </article>
    );
});

// ─────────────────────────────────────────────────────────────────────────────
// Info field (in the expanded strip)
// ─────────────────────────────────────────────────────────────────────────────

function InfoField({
    label,
    value,
    mono = false,
}: {
    label: string;
    value?: string | null;
    mono?: boolean;
}) {
    return (
        <div className="min-w-0">
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                {label}
            </div>
            <div
                className={cn(
                    "mt-0.5 truncate text-sm font-medium",
                    mono ? "font-mono text-foreground" : "text-foreground",
                    !value && "text-muted-foreground/50"
                )}
                title={value || ""}
            >
                {value || "—"}
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Skeleton loading state
// ─────────────────────────────────────────────────────────────────────────────

function LicenseSkeleton() {
    return (
        <div className="space-y-2">
            {[80, 65, 90, 70, 75].map((w, i) => (
                <div key={i} className="overflow-hidden rounded-2xl border border-border/60 bg-card p-4">
                    <div className="flex items-center gap-4">
                        <Skeleton className="h-5 rounded" style={{ width: `${w * 2}px` }} />
                        <Skeleton className="h-3.5 w-24 rounded" />
                        <Skeleton className="h-3.5 w-28 rounded" />
                        <Skeleton className="ml-auto h-5 w-16 rounded-full" />
                        <Skeleton className="h-4 w-20 rounded" />
                        <Skeleton className="h-4 w-4 rounded" />
                    </div>
                </div>
            ))}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Root: LicensesTable
// ─────────────────────────────────────────────────────────────────────────────

export default function LicensesTable({
    loading,
    data,
    canWrite,
    entityName,
    filterParams,
    currentPage,
    pageSize,
    navigate,
    onDelete,
    onViewBalance,
    onPlanLicense,
    onViewOwnership,
    fetchingOwnershipIds,
    onFetchOwnership,
}: LicensesTableProps) {
    // Only one accordion open at a time
    const [expandedId, setExpandedId] = useState<number | null>(null);

    const handleToggle = useCallback((id: number) => {
        setExpandedId((prev) => (prev === id ? null : id));
    }, []);

    if (loading) return <LicenseSkeleton />;

    if (data.length === 0) {
        return (
            <div className="flex flex-col items-center py-16 text-center">
                <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-muted">
                    <Inbox className="size-7 text-muted-foreground/50" aria-hidden="true" />
                </div>
                <h3 className="text-base font-semibold text-foreground">No licenses found</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                    Try adjusting your search or filters.
                </p>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-2" role="list" aria-label="Licenses">
            {data.map((item) => (
                <LicenseRow
                    key={item.id}
                    item={item}
                    expanded={expandedId === item.id}
                    onToggle={() => handleToggle(item.id)}
                    canWrite={canWrite}
                    entityName={entityName}
                    filterParams={filterParams}
                    currentPage={currentPage}
                    pageSize={pageSize}
                    navigate={navigate}
                    onDelete={onDelete}
                    onViewBalance={onViewBalance}
                    onPlanLicense={onPlanLicense}
                    onViewOwnership={onViewOwnership}
                    isFetchingDGFT={fetchingOwnershipIds.has(item.id)}
                    onFetchDGFT={onFetchOwnership}
                />
            ))}
        </div>
    );
}
