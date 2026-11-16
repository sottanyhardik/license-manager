import { cn } from "@/lib/utils";
import DetailTable from "@/components/primitives/DetailTable";
import { openLicenseCopyPdf } from "@/utils/licenseCopyPdf";
import { formatTruthyIndianNumber, formatTruthyInr } from "@/pages/masters/masterDisplayFormatters";
import type { AllotmentDetailRow } from "../types";

type Props = { rows: AllotmentDetailRow[] };

const fmtInr = (val) => formatTruthyInr(val);
const fmtQty = (val) => formatTruthyIndianNumber(val, { maximumFractionDigits: 3 });

/**
 * "Allotment Details" tab: the list row's `allotment_details`, moved verbatim
 * from the former expanded body of AllotmentsTable (same columns/formatting,
 * no extra request).
 */
export function AllotmentItemsTab({ rows }: Props) {
    return (
        <DetailTable
            columns={[
                { key: 'license_number',     label: 'License',     bold: true, nowrap: true,
                    render: (v, row) => v && row.license_id ? (
                        <button
                            type="button"
                            onClick={() => openLicenseCopyPdf(row.license_id, v)}
                            className={cn('text-primary', 'hover:underline underline-offset-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring', 'cursor-pointer')}
                            title="Open License Copy PDF"
                            aria-label={`Open License Copy PDF for ${v}`}
                        >
                            {v}
                        </button>
                    ) : (
                        <span className="text-primary">{v || '—'}</span>
                    ) },
                { key: 'serial_number',      label: 'Sl#',         align: 'right', nowrap: true },
                { key: 'product_description', label: 'Item',       muted: true },
                { key: 'qty',                 label: 'Qty',        align: 'right', nowrap: true,
                    render: v => fmtQty(v) },
                { key: 'cif_fc',              label: 'CIF (FC)',   align: 'right', nowrap: true,
                    render: v => formatTruthyIndianNumber(v, { maximumFractionDigits: 2 }) },
                { key: 'cif_inr',             label: 'CIF (INR)',  align: 'right', nowrap: true, bold: true,
                    render: v => fmtInr(v) },
            ]}
            rows={rows}
            emptyMessage="No items have been allotted yet."
        />
    );
}
