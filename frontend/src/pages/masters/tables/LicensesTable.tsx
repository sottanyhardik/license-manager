import {
    BookCheck, Calendar, CalendarX, CloudDownload, Eye, FileSpreadsheet,
    FileText, Inbox, MapPin, MoreHorizontal, Network, Pencil, RefreshCw,
    Target, Trash2,
} from "lucide-react";
import { toast } from "sonner";
import api from "../../../api/axios";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { openPdfPreview } from "../../../utils/pdfPreview";
import { saveFilterState } from "../../../utils/filterPersistence";

interface LicensesTableProps {
    loading: boolean;
    data: any[];
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, any>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: any) => void;
    onViewBalance: (licenseId: number) => void;
    onPlanLicense: (license: { id: number; number: string; balance: number }) => void;
    onViewOwnership: (license: { id: number; number: string }) => void;
    fetchingOwnershipIds: Set<number>;
    onFetchOwnership: (item: any) => void;
    invalidateList: () => void;
}

/** Format a numeric value as Indian Rupees — e.g. ₹1,23,456 */
function fmtInr(val: any): string {
    if (!val && val !== 0) return "—";
    const n = Number(val);
    if (isNaN(n)) return "—";
    return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/** Parse dd-MM-yyyy date string into a Date object */
function parseIndianDate(s: string | null | undefined): Date | null {
    if (!s) return null;
    const p = s.split("-");
    return p.length === 3 ? new Date(Number(p[2]), Number(p[1]) - 1, Number(p[0])) : null;
}

/** Return Tailwind classes for the purchase-status badge */
function statusBadgeCls(code: string | null | undefined): string {
    if (code === "E1") return "bg-primary/10 text-primary ring-1 ring-primary/20";
    if (code === "E5") return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200";
    return "bg-muted text-muted-foreground ring-1 ring-border";
}

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
    if (loading) {
        return (
            <div className="py-10 text-center">
                <span className="inline-block size-6 animate-spin rounded-full border-2 border-current border-t-transparent text-primary" aria-hidden="true" />
                <div className="mt-2 text-sm text-muted-foreground">Loading licenses…</div>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="py-10 text-center">
                <Inbox className="mx-auto size-8 text-muted-foreground/40" aria-hidden="true" />
                <div className="mt-3 text-sm font-medium text-muted-foreground">No licenses found</div>
                <div className="mt-1 text-xs text-muted-foreground/70">Try adjusting your filters or search.</div>
            </div>
        );
    }

    const navigateToEdit = (id: number) => {
        saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: "" });
        navigate(`/licenses/${id}/edit`);
    };

    const handleDownloadPdf = async (item: any) => {
        try {
            const r = await api.get(`licenses/${item.id}/balance-pdf/`, {
                responseType: "blob",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            openPdfPreview(r.data, `${item.license_number || item.id}-balance.pdf`);
        } catch (err: any) {
            toast.error(err?.response?.data?.error || "Failed to generate PDF");
        }
    };

    const handleDownloadExcel = async (item: any) => {
        try {
            const r = await api.get(`licenses/${item.id}/balance-excel/`, {
                responseType: "blob",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            const blob = new Blob([r.data], {
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
        } catch (err: any) {
            toast.error(err?.response?.data?.error || "Failed to generate Excel");
        }
    };

    const handleViewDocuments = async (item: any) => {
        try {
            const r = await api.get(`licenses/${item.id}/merged-documents/`, {
                responseType: "blob",
                headers: { Authorization: `Bearer ${localStorage.getItem("access")}` },
            });
            openPdfPreview(r.data, `${item.license_number || item.id}-copy.pdf`);
        } catch (err: any) {
            if (err.response?.status === 404) {
                toast.warning("Document files are not available on this server.");
            } else {
                toast.error(err.response?.data ? String(err.response.data).slice(0, 200) : "Failed to load documents");
            }
        }
    };

    return (
        <div className="flex flex-col gap-2">
            {data.map((item) => {
                const isExpired = !!(item.license_expiry_date && parseIndianDate(item.license_expiry_date)! < new Date());
                const isFetching = fetchingOwnershipIds.has(item.id);

                return (
                    <article
                        key={item.id}
                        aria-label={`License ${item.license_number || item.id}`}
                        className={cn(
                            "overflow-hidden rounded-xl border-l-4 shadow-sm transition-shadow hover:shadow-md",
                            isExpired
                                ? "border border-destructive/30 border-l-destructive bg-destructive/[0.02]"
                                : item.is_manually_planned
                                    ? "border border-emerald-200 border-l-emerald-500 bg-emerald-50/30"
                                    : "border border-border/70 border-l-primary bg-card"
                        )}
                    >
                        {/* ── Identity row ──────────────────────────────────── */}
                        <header className="flex flex-wrap items-center gap-2 border-b border-border/50 bg-muted/40 px-4 py-2.5">
                            {/* License number — primary anchor */}
                            <span className="mr-0.5 font-mono text-[15px] font-bold tracking-tight text-foreground">
                                {item.license_number || "—"}
                            </span>

                            {/* State chips */}
                            {isExpired && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[11px] font-semibold text-destructive ring-1 ring-destructive/20">
                                    <CalendarX className="size-3" aria-hidden="true" />Expired
                                </span>
                            )}
                            {item.is_manually_planned && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
                                    <Target className="size-3" aria-hidden="true" />Planned
                                </span>
                            )}

                            {/* Date chips */}
                            {item.license_date && (
                                <span className="chip chip-neutral">
                                    <Calendar className="size-3" aria-hidden="true" />{item.license_date}
                                </span>
                            )}
                            {item.license_expiry_date && !isExpired && (
                                <span className="chip chip-neutral">
                                    <CalendarX className="size-3" aria-hidden="true" />Exp: {item.license_expiry_date}
                                </span>
                            )}
                            {item.ledger_date && (
                                <span className="chip chip-success">
                                    <BookCheck className="size-3" aria-hidden="true" />Ledger: {item.ledger_date}
                                </span>
                            )}
                            {item.port_name && (
                                <span className="chip chip-info">
                                    <MapPin className="size-3" aria-hidden="true" />{item.port_name}
                                </span>
                            )}

                            {/* Purchase status badge */}
                            {item.purchase_status_label && (
                                <span className={cn(
                                    "rounded-full px-2 py-0.5 text-[11px] font-semibold",
                                    statusBadgeCls(item.purchase_status_code)
                                )}>
                                    {item.purchase_status_label}
                                </span>
                            )}

                            {/* Document availability — moved to header as a quick chip */}
                            {(item.has_tl || item.has_copy) && (
                                <button
                                    type="button"
                                    onClick={() => handleViewDocuments(item)}
                                    className="chip chip-success cursor-pointer border-0 transition-opacity hover:opacity-80"
                                    aria-label={`View copy document for ${item.license_number}`}
                                >
                                    <FileText className="size-3" aria-hidden="true" />Copy
                                </button>
                            )}
                            {item.has_condition_sheet && (
                                <span className="chip chip-primary">
                                    <FileText className="size-3" aria-hidden="true" />Cond. Sheet
                                </span>
                            )}
                        </header>

                        {/* ── Info row ──────────────────────────────────────── */}
                        <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-b border-border/50 bg-card px-4 py-3 sm:grid-cols-4">
                            <MetaField label="Norm Class" value={item.get_norm_class} mono />
                            <MetaField label="Exporter" value={item.exporter_name} />
                            <MetaField label="IEC" value={item.exporter_iec} mono />
                            <MetaField label="Transfer Status" value={item.latest_transfer} />
                        </div>

                        {/* ── Action bar ────────────────────────────────────── */}
                        <footer className="flex flex-wrap items-center justify-between gap-2 bg-muted/40 px-4 py-2">
                            {/* Balance stat */}
                            <div className="flex items-baseline gap-1.5">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Balance CIF</span>
                                <span className="text-sm font-bold tabular-nums text-foreground">{fmtInr(item.get_balance_cif)}</span>
                            </div>

                            {/* Actions */}
                            <div className="flex shrink-0 items-center gap-1.5">
                                {/* Primary: Edit */}
                                {canWrite && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => navigateToEdit(item.id)}
                                        className="h-7 gap-1.5 px-2.5 text-xs"
                                        aria-label={`Edit license ${item.license_number}`}
                                    >
                                        <Pencil className="size-3.5" aria-hidden="true" />
                                        Edit
                                    </Button>
                                )}

                                {/* View Balance — always visible, key action */}
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => onViewBalance(item.id)}
                                    className="h-7 gap-1.5 px-2.5 text-xs"
                                    aria-label={`View balance for ${item.license_number}`}
                                >
                                    <Eye className="size-3.5" aria-hidden="true" />
                                    Balance
                                </Button>

                                {/* Secondary: dropdown */}
                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-7 w-7 p-0"
                                            aria-label={`More actions for license ${item.license_number}`}
                                        >
                                            <MoreHorizontal className="size-3.5" aria-hidden="true" />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end" className="w-52">
                                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                                        <DropdownMenuSeparator />

                                        {/* Planning */}
                                        {canWrite && (
                                            <DropdownMenuItem
                                                onClick={() => onPlanLicense({
                                                    id: item.id,
                                                    number: item.license_number,
                                                    balance: Number(item.get_balance_cif || 0),
                                                })}
                                            >
                                                <Target className="size-4" aria-hidden="true" />
                                                Plan Utilization
                                            </DropdownMenuItem>
                                        )}

                                        {/* Ownership */}
                                        <DropdownMenuItem
                                            onClick={() => onViewOwnership({ id: item.id, number: item.license_number })}
                                        >
                                            <Network className="size-4" aria-hidden="true" />
                                            View Ownership
                                        </DropdownMenuItem>

                                        <DropdownMenuSeparator />

                                        {/* Downloads */}
                                        <DropdownMenuItem onClick={() => handleDownloadPdf(item)}>
                                            <FileText className="size-4" aria-hidden="true" />
                                            Download Balance PDF
                                        </DropdownMenuItem>
                                        <DropdownMenuItem onClick={() => handleDownloadExcel(item)}>
                                            <FileSpreadsheet className="size-4" aria-hidden="true" />
                                            Download Balance Excel
                                        </DropdownMenuItem>

                                        {/* Fetch from DGFT */}
                                        {canWrite && (
                                            <>
                                                <DropdownMenuSeparator />
                                                <DropdownMenuItem
                                                    disabled={isFetching}
                                                    onClick={() => onFetchOwnership(item)}
                                                >
                                                    {isFetching
                                                        ? <RefreshCw className="size-4 animate-spin" aria-hidden="true" />
                                                        : <CloudDownload className="size-4" aria-hidden="true" />}
                                                    {isFetching ? "Fetching…" : "Fetch from DGFT"}
                                                </DropdownMenuItem>
                                            </>
                                        )}

                                        {/* Destructive actions */}
                                        {canWrite && (
                                            <>
                                                <DropdownMenuSeparator />
                                                <DropdownMenuItem
                                                    onClick={() => onDelete(item)}
                                                    className="text-destructive focus:text-destructive"
                                                >
                                                    <Trash2 className="size-4" aria-hidden="true" />
                                                    Delete
                                                </DropdownMenuItem>
                                            </>
                                        )}
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>
                        </footer>
                    </article>
                );
            })}
        </div>
    );
}

/** A labelled meta field for the info row */
function MetaField({
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
            <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                {label}
            </div>
            <div
                title={value || ""}
                className={cn(
                    "truncate text-sm font-medium text-foreground",
                    mono && "font-mono",
                    !value && "text-muted-foreground/50"
                )}
            >
                {value || "—"}
            </div>
        </div>
    );
}
