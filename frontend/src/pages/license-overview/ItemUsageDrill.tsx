import { AlertTriangle, Loader2 } from "lucide-react";

import { fmtDate, fmtNum } from "./licenseOverviewHelpers";
import { useItemUsage, type UsageType } from "./useLicenceModalParity";

interface ItemUsageDrillProps {
    licenseId: string | number;
    itemId: number;
    type: UsageType;
}

const num = (value: number | string | null | undefined) => (value == null || value === "" ? "—" : fmtNum(Number(value), 2));

/** Same columns as the modal's drill (`LicenseBalanceModal.tsx:636, :671`). Server values only, no balance line. */
const USAGE_BOE_COLUMNS = ["BOE Number", "Date", "Port", "Company", "Qty", "CIF $", "CIF INR"] as const;
const USAGE_ALLOTMENT_COLUMNS = ["Company", "Qty", "CIF $", "CIF INR"] as const;

const th = "px-2 py-1.5 text-left font-semibold";
const td = "px-2 py-1.5";

export default function ItemUsageDrill({ licenseId, itemId, type }: ItemUsageDrillProps) {
    const { data, isLoading, isError } = useItemUsage(licenseId, itemId, type, true);

    if (isLoading) {
        return <p className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> Loading usage…</p>;
    }
    if (isError || !data) {
        return <p className="flex items-center gap-2 text-xs text-destructive"><AlertTriangle className="size-3.5" aria-hidden="true" /> Failed to load usage details.</p>;
    }

    return (
        <div className="space-y-3 text-xs">
            <section aria-label="BOE usage">
                <h5 className="mb-1 font-semibold">BOEs</h5>
                {data.boes.length > 0 ? (
                    <table className="w-full rounded border border-border/70 bg-card">
                        <thead className="bg-muted/60 text-muted-foreground"><tr>{USAGE_BOE_COLUMNS.map((c) => <th key={c} scope="col" className={th}>{c}</th>)}</tr></thead>
                        <tbody>
                            {data.boes.map((boe) => (
                                <tr key={boe.id} className="border-t border-border/50">
                                    <td className={td}>{boe.bill_of_entry_number ?? "—"}</td>
                                    <td className={td}>{fmtDate(boe.date)}</td>
                                    <td className={td}>{boe.port || "—"}</td>
                                    <td className={td}>{boe.company || "—"}</td>
                                    <td className={`${td} tabular-nums`}>{num(boe.quantity)}</td>
                                    <td className={`${td} tabular-nums`}>{num(boe.cif_fc)}</td>
                                    <td className={`${td} tabular-nums`}>{num(boe.cif_inr)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : <p className="text-muted-foreground">No BOE usage found</p>}
            </section>
            <section aria-label="Allotment usage">
                <h5 className="mb-1 font-semibold">Allotments</h5>
                {data.allotments.length > 0 ? (
                    <table className="w-full rounded border border-border/70 bg-card">
                        <thead className="bg-muted/60 text-muted-foreground"><tr>{USAGE_ALLOTMENT_COLUMNS.map((c) => <th key={c} scope="col" className={th}>{c}</th>)}</tr></thead>
                        <tbody>
                            {data.allotments.map((a) => (
                                <tr key={a.id} className="border-t border-border/50">
                                    <td className={td}>{a.company || "—"}</td>
                                    <td className={`${td} tabular-nums`}>{num(a.quantity)}</td>
                                    <td className={`${td} tabular-nums`}>{num(a.cif_fc)}</td>
                                    <td className={`${td} tabular-nums`}>{num(a.cif_inr)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : <p className="text-muted-foreground">No Allotment usage found</p>}
            </section>
        </div>
    );
}
