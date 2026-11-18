import { useQuery } from "@tanstack/react-query";

import api from "@/api/axios";
import DetailTable from "@/components/primitives/DetailTable";
import { QueryBoundary } from "@/components/shared";
import { displayValue } from "@/lib/display";
import { formatTruthyIndianNumber, formatTruthyInr } from "@/pages/masters/masterDisplayFormatters";

type BoeRow = Record<string, unknown> & { id: number };

/**
 * BOE: bills of entry linked to this allotment (`bill-of-entries/?allotment=`),
 * as returned by the BOE register — BOE permissions apply, and totals are the
 * BOE serializer's own (frozen ledger rows included exactly as the register shows them).
 */
export function BoeTab({ id }: { id: number }) {
    const query = useQuery({
        queryKey: ["allotment-boes", id],
        queryFn: async ({ signal }) => {
            const { data } = await api.get("bill-of-entries/", { params: { allotment: id, page_size: 100 }, signal });
            return (data?.results ?? data ?? []) as BoeRow[];
        },
        staleTime: 30_000,
    });
    return (
        <QueryBoundary query={query} rows={3} loadingLabel="Loading bills of entry" errorTitle="Could not load bills of entry">
            {(rows) => (
                <DetailTable
                    columns={[
                        { key: "bill_of_entry_number", label: "BOE No.", bold: true, nowrap: true, render: (v) => <span className="font-mono">{displayValue(v)}</span> },
                        { key: "bill_of_entry_date", label: "BOE Date", nowrap: true, render: (v) => displayValue(v) },
                        { key: "port_name", label: "Port", nowrap: true, render: (v) => displayValue(v) },
                        { key: "company_name", label: "Company", render: (v) => displayValue(v) },
                        { key: "invoice_no", label: "Invoice No.", nowrap: true, render: (v) => displayValue(v) },
                        { key: "total_quantity", label: "Qty", align: "right", nowrap: true, render: (v) => formatTruthyIndianNumber(v as string, { maximumFractionDigits: 3 }) },
                        { key: "total_fc", label: "CIF (FC)", align: "right", nowrap: true, render: (v) => formatTruthyIndianNumber(v as string, { maximumFractionDigits: 2 }) },
                        { key: "total_inr", label: "CIF (INR)", align: "right", nowrap: true, render: (v) => formatTruthyInr(v as string) },
                        { key: "invoice_status_label", label: "Status", nowrap: true, render: (v) => displayValue(v) },
                    ]}
                    rows={rows}
                    emptyMessage="No bills of entry are linked to this allotment."
                />
            )}
        </QueryBoundary>
    );
}
