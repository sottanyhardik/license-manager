import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import api from "@/api/axios";
import { fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";

interface CustomsImportItem {
    id: number;
    description?: string | null;
    items_detail?: { id: number; name: string }[];
    quantity?: number | null;
    allotted_quantity?: number | null;
    debited_quantity?: number | null;
    available_quantity?: number | null;
    cif_fc?: number | null;
    balance_cif_fc?: number | null;
}

interface CustomsLedgerSectionProps {
    licenseId: string | number;
}

function itemLabel(item: CustomsImportItem): string {
    if (item.items_detail && item.items_detail.length > 0) {
        return item.items_detail.map((d) => d.name).join(", ");
    }
    return item.description || "-";
}

/**
 * Overview tab's Customs Ledger — Item Detail section.
 *
 * `LicenseBalanceModal.tsx`'s Export/Import item tables are tightly coupled
 * to that modal's local inline-editing state (item tags, condition-type
 * select, expand/usage-fetch) — extracting them cleanly without dragging
 * that state along would be a much larger refactor than this workspace
 * warrants. Per the brief's explicit fallback, this renders a simplified,
 * REAL (not placeholder) view of the same `licenses/{id}/` data: per-item
 * Available/Debited/Allotted/Balance CIF, read-only.
 *
 * Relocated (unchanged) from `pages/license-balance/`.
 */
export default function CustomsLedgerSection({ licenseId }: CustomsLedgerSectionProps) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ["license-balance-customs-ledger", String(licenseId)],
        queryFn: async () => {
            const { data } = await api.get(`licenses/${licenseId}/`);
            return data as { import_license?: CustomsImportItem[] };
        },
    });

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading customs ledger…
            </div>
        );
    }
    if (isError) {
        return <p className="py-4 text-sm text-destructive">Failed to load customs ledger data.</p>;
    }

    const items = data?.import_license ?? [];

    return (
        <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
                <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                        <th scope="col" className="px-3 py-2 text-left font-semibold">Item</th>
                        <th scope="col" className="px-3 py-2 text-right font-semibold">Total Qty</th>
                        <th scope="col" className="px-3 py-2 text-right font-semibold">Allotted Qty</th>
                        <th scope="col" className="px-3 py-2 text-right font-semibold">Debited Qty</th>
                        <th scope="col" className="px-3 py-2 text-right font-semibold">Available Qty</th>
                        <th scope="col" className="px-3 py-2 text-right font-semibold">CIF FC</th>
                        <th scope="col" className="px-3 py-2 text-right font-semibold">Balance CIF FC</th>
                    </tr>
                </thead>
                <tbody>
                    {items.length === 0 && (
                        <tr>
                            <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                                No import items on this licence.
                            </td>
                        </tr>
                    )}
                    {items.map((item) => (
                        <tr key={item.id} className="border-t border-border/60">
                            <td className="px-3 py-2">{itemLabel(item)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(item.quantity)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(item.allotted_quantity)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(item.debited_quantity)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(item.available_quantity)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(item.cif_fc)}</td>
                            <td className="px-3 py-2 text-right font-medium">{fmtNum(item.balance_cif_fc)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
