import { useMemo, useState } from "react";
import { AlertTriangle, ClipboardCopy, Loader2, Receipt } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import DebouncedSearchInput from "@/components/DebouncedSearchInput";
import { useLicenseOverviewBoes } from "./useLicenseOverviewBoes";
import { extractApiError, fmtDate, fmtNum, overviewBoeStatusVariant, sortRows, type SortState } from "./licenseOverviewHelpers";
import SortableHeader from "./SortableHeader";
import type { LicenseOverviewBoeRow } from "./types";

interface BoesTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

type SortKey = keyof LicenseOverviewBoeRow;

// Cards when the count is small enough to browse visually, dense table
// otherwise — same threshold convention as `LedgerTab.tsx`'s `BoeSection`
// (`CARD_THRESHOLD = 10`). Licenses can have 1000+ BOEs, so in practice this
// tab almost always renders in table mode.
const CARD_THRESHOLD = 10;

async function copyToClipboard(text: string) {
    try {
        await navigator.clipboard.writeText(text);
        toast.success("Copied");
    } catch {
        toast.error("Failed to copy");
    }
}

function matchesSearch(row: LicenseOverviewBoeRow, term: string): boolean {
    if (!term) return true;
    const haystack = [row.bill_of_entry_number, row.supplier, row.invoice_no].filter(Boolean).join(" ").toLowerCase();
    return haystack.includes(term);
}

/**
 * BOEs tab — one row per distinct BOE linked to this license, from
 * `GET /licenses/<id>/overview-boes/`. No "Duty Saved" column — no such
 * field exists anywhere in the schema.
 *
 * Render pattern (cards for small counts, dense table for large ones)
 * copied from `LedgerTab.tsx`'s private `BoeSection`, not imported from it.
 * No pagination/virtualization library is used, matching this codebase's
 * existing convention everywhere else — payload is small JSON even at 1000
 * rows.
 */
export default function BoesTab({ licenseId, isActive }: BoesTabProps) {
    const { data, isLoading, isError, error } = useLicenseOverviewBoes(licenseId, isActive);
    const [search, setSearch] = useState("");
    // Latest BOE first is the business default. Users can still reverse it
    // or choose another column through the sortable table headers.
    const [sort, setSort] = useState<SortState<SortKey>>({ key: "bill_of_entry_date", direction: "desc" });

    const handleSort = (key: SortKey) => {
        setSort((prev) => ({
            key,
            direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
        }));
    };

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase();
        return (data ?? []).filter((row) => matchesSearch(row, term));
    }, [data, search]);

    const rows = useMemo(
        () => sortRows(filtered, sort, (row, key) => row[key] as string | number | null),
        [filtered, sort]
    );

    if (!isActive) return null;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading BOEs…
            </div>
        );
    }

    if (isError) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load BOEs.")}</AlertDescription>
            </Alert>
        );
    }

    const allBoes = data ?? [];
    const totalCif = rows.reduce((s, b) => s + (Number(b.cif_fc) || 0), 0);

    return (
        <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 bg-card px-3 py-2">
                <div className="flex items-center gap-2">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-amber-100 dark:bg-amber-500/15">
                        <Receipt className="size-3.5 text-amber-700 dark:text-amber-400" aria-hidden="true" />
                    </span>
                    <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Bills of Entry</span>
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10.5px] font-semibold text-amber-700 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/20">
                        {allBoes.length} total{search ? `, ${rows.length} shown` : ""}
                    </span>
                </div>
                <div className="w-full max-w-xs sm:w-64">
                    <DebouncedSearchInput
                        value={search}
                        onChange={setSearch}
                        placeholder="Search BOE / supplier / invoice…"
                    />
                </div>
            </div>

            {allBoes.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">No BOEs linked to this licence.</p>
            ) : rows.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">No BOEs match “{search}”.</p>
            ) : allBoes.length <= CARD_THRESHOLD ? (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3">
                    {rows.map((b, idx) => (
                        <div key={`${b.bill_of_entry_number}-${idx}`} className="group rounded-xl border border-border/60 bg-card p-3 transition-shadow hover:shadow-sm">
                            <div className="mb-2 flex items-start justify-between gap-2">
                                <div className="flex items-center gap-1.5">
                                    <span className="font-mono text-sm font-semibold text-foreground">{b.bill_of_entry_number || "—"}</span>
                                    {b.bill_of_entry_number && (
                                        <button
                                            type="button"
                                            onClick={() => copyToClipboard(b.bill_of_entry_number!)}
                                            className="text-muted-foreground/50 hover:text-muted-foreground cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                                            title="Copy BOE number"
                                        >
                                            <ClipboardCopy className="size-3" />
                                        </button>
                                    )}
                                </div>
                                <Badge variant={overviewBoeStatusVariant(b.status)}>{b.status}</Badge>
                            </div>
                            <div className="mb-1.5 truncate text-xs text-muted-foreground" title={b.supplier || ""}>{b.supplier || "—"}</div>
                            <div className="mb-2 text-[10.5px] text-muted-foreground/70">
                                {fmtDate(b.bill_of_entry_date)}
                                {b.port ? ` · ${b.port}` : ""}
                            </div>
                            <div className="grid grid-cols-2 gap-2 border-t border-border/40 pt-2 text-[10.5px] text-muted-foreground">
                                <div>Invoice: {b.invoice_no || "—"}</div>
                                <div>{fmtDate(b.invoice_date)}</div>
                            </div>
                            <div className="mt-2 flex items-center justify-between rounded-lg bg-amber-50/60 px-2 py-1 dark:bg-amber-500/10">
                                <span className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">CIF</span>
                                <span className="tabular-nums text-[11.5px] font-bold text-amber-700 dark:text-amber-400">{fmtNum(b.cif_fc)}</span>
                            </div>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="max-h-[calc(100vh-19rem)] overflow-auto rounded-lg border border-border/70 bg-card">
                    <table className="w-full min-w-[900px] text-[13px]">
                        <thead className="sticky top-0 z-[1] bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground backdrop-blur">
                            <tr>
                                <SortableHeader label="BOE No." sortKey="bill_of_entry_number" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Date" sortKey="bill_of_entry_date" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Port" sortKey="port" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Supplier" sortKey="supplier" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Invoice Number" sortKey="invoice_no" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Invoice Date" sortKey="invoice_date" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="CIF" sortKey="cif_fc" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                                <SortableHeader label="Status" sortKey="status" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((b, idx) => (
                                <tr key={`${b.bill_of_entry_number}-${idx}`} className="border-t border-border/60 hover:bg-muted/30">
                                    <td className="px-3 py-1.5 font-mono text-[10.5px]">{b.bill_of_entry_number || "—"}</td>
                                    <td className="whitespace-nowrap px-3 py-1.5 text-[10.5px]">{fmtDate(b.bill_of_entry_date)}</td>
                                    <td className="px-3 py-1.5 text-[10.5px]">{b.port || "—"}</td>
                                    <td className="px-3 py-1.5 text-[10.5px]">{b.supplier || "—"}</td>
                                    <td className="px-3 py-1.5 text-[10.5px]">{b.invoice_no || "—"}</td>
                                    <td className="whitespace-nowrap px-3 py-1.5 text-[10.5px]">{fmtDate(b.invoice_date)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums text-[10.5px]">{fmtNum(b.cif_fc)}</td>
                                    <td className="px-3 py-1.5">
                                        <Badge variant={overviewBoeStatusVariant(b.status)}>{b.status}</Badge>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {rows.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning/20 bg-warning/5 px-3 py-2">
                    <span className="text-[10.5px] font-bold uppercase tracking-widest text-amber-700 dark:text-amber-400">
                        Total CIF{search ? " (filtered)" : ""}
                    </span>
                    <span className="text-base font-bold tabular-nums text-amber-700 dark:text-amber-400">{fmtNum(totalCif)}</span>
                </div>
            )}
        </div>
    );
}
