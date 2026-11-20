import { useEffect, useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import api from "@/api/axios";
import { buildItemReportProductDrilldownPath } from "../reportPaths";
import type { ReportFilterValues } from "./reportQueryString";
import type { DrilldownLicence, ProductDrilldown as DrilldownData } from "./productTypes";
import { formatDecimal } from "./productFormat";

type Props = { productKey: string; filters: ReportFilterValues };

function Figure({ label, value }: { label: string; value: string | null }) {
    return (
        <div className="flex flex-col">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="font-medium tabular-nums">{formatDecimal(value)}</dd>
        </div>
    );
}

function Refs({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
    return (
        <div>
            <h4 className="text-xs font-semibold uppercase text-muted-foreground">{title}</h4>
            {empty ? <p className="text-xs text-muted-foreground">None</p> : <ul className="mt-1 space-y-0.5 text-xs">{children}</ul>}
        </div>
    );
}

function LicenceBlock({ licence }: { licence: DrilldownLicence }) {
    return (
        <section aria-label={`Licence ${licence.license_number}`} className="rounded-lg border border-border bg-card p-3">
            <h3 className="text-sm font-semibold">Licence {licence.license_number}</h3>
            <dl className="mt-2 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:grid-cols-8">
                <Figure label="Debited Qty" value={licence.debited_qty} />
                <Figure label="Debited CIF" value={licence.debited_cif} />
                <Figure label="Allotted Qty" value={licence.allotted_qty} />
                <Figure label="Allotted CIF" value={licence.allotted_cif} />
                <Figure label="Invoice Qty" value={licence.invoice_qty} />
                <Figure label="Invoice CIF" value={licence.invoice_cif} />
                <Figure label="Balance Qty" value={licence.balance_qty} />
                <Figure label="Balance CIF" value={licence.balance_cif} />
            </dl>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                <Refs title="Import items" empty={licence.import_items.length === 0}>
                    {licence.import_items.map((it) => (
                        <li key={it.import_item_id}>
                            #{it.serial_number ?? "—"} {it.description} · HSN {it.hs_code || "—"} · Norm {it.norm || "—"} · {formatDecimal(it.total_qty)} {it.unit} · CIF {formatDecimal(it.total_cif)}
                        </li>
                    ))}
                </Refs>
                <Refs title="Bills of entry" empty={licence.boes.length === 0}>
                    {licence.boes.map((b) => (
                        <li key={`${b.boe_id}-${b.row_id}`}>
                            {b.bill_of_entry_number}{b.date ? ` (${b.date})` : ""} · Qty {formatDecimal(b.qty)} · CIF {formatDecimal(b.cif)}
                            {b.share != null ? ` · Share ${b.share}` : ""}
                        </li>
                    ))}
                </Refs>
                <Refs title="Allotments" empty={licence.allotments.length === 0}>
                    {licence.allotments.map((a) => (
                        <li key={`${a.allotment_id}-${a.row_id}`}>
                            {a.reference} · Qty {formatDecimal(a.qty)} · CIF {formatDecimal(a.cif)} · Outstanding {formatDecimal(a.outstanding)}
                        </li>
                    ))}
                </Refs>
                <Refs title="Invoices" empty={licence.invoices.length === 0}>
                    {licence.invoices.map((i) => (
                        <li key={`${i.invoice_id}-${i.line_id}`}>
                            {i.invoice_number}{i.date ? ` (${i.date})` : ""} · Qty {formatDecimal(i.qty)} · CIF {formatDecimal(i.cif)}
                            {i.share != null ? ` · Share ${i.share}` : ""}
                        </li>
                    ))}
                </Refs>
            </div>
        </section>
    );
}

/** Licence-level drill-down for one product row — fetched when the row is expanded. */
export default function ProductDrilldown({ productKey, filters }: Props) {
    const [state, setState] = useState<{ status: "loading" | "error" | "ready"; data?: DrilldownData }>({ status: "loading" });

    useEffect(() => {
        let cancelled = false;
        setState({ status: "loading" });
        api.get(buildItemReportProductDrilldownPath(productKey, { format: "json", ...filters }))
            .then((response) => { if (!cancelled) setState({ status: "ready", data: response.data as DrilldownData }); })
            .catch(() => { if (!cancelled) setState({ status: "error" }); });
        return () => { cancelled = true; };
    }, [productKey, filters]);

    if (state.status === "loading") {
        return (
            <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Loading licences…
            </p>
        );
    }
    if (state.status === "error" || !state.data) {
        return <p role="alert" className="text-sm text-destructive">Failed to load licence details. Collapse and expand the row to retry.</p>;
    }
    if (state.data.licences.length === 0) {
        return <p className="text-sm text-muted-foreground">No licences for this product.</p>;
    }
    return (
        <div className="space-y-3">
            {state.data.licences.map((licence) => <LicenceBlock key={licence.license_id} licence={licence} />)}
        </div>
    );
}
