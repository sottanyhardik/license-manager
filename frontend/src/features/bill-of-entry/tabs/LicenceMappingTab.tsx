import DetailTable from "@/components/primitives/DetailTable";
import { openLicenseCopyPdf } from "@/utils/licenseCopyPdf";

import { displayValue } from "@/lib/display";
import type { BoeDetailRow } from "../types";

/**
 * Which licence row each BOE item debits, from the row's own `item_details`
 * (RowDetailsSerializer). No request; every value is shown as received.
 */
export function LicenceMappingTab({ rows }: { rows: BoeDetailRow[] }) {
    return (
        <DetailTable
            emptyMessage="No licence rows are mapped to this BOE."
            columns={[
                { key: "license_number", label: "License", bold: true, nowrap: true,
                    render: (v: unknown, row: BoeDetailRow) => v && row.license_id ? (
                        <button
                            type="button"
                            onClick={() => { void openLicenseCopyPdf(row.license_id as number, String(v)); }}
                            className="cursor-pointer text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            aria-label={`Open License Copy PDF for ${String(v)}`}
                        >
                            {String(v)}
                        </button>
                    ) : displayValue(v) },
                { key: "item_serial_number", label: "Sr No", nowrap: true, render: (v: unknown) => displayValue(v) },
                { key: "item_description", label: "Item", muted: true, render: (v: unknown) => displayValue(v) },
                { key: "condition_type", label: "Condition", nowrap: true, render: (v: unknown) => displayValue(v) },
                { key: "purchase_status", label: "Purchase Status", nowrap: true, render: (v: unknown) => displayValue(v) },
                { key: "is_dispute", label: "Dispute", nowrap: true, render: (v: unknown) => displayValue(Boolean(v)) },
                { key: "authoritative_available_cif", label: "Available CIF (licence row)", align: "right", nowrap: true, render: (v: unknown) => displayValue(v) },
            ]}
            rows={rows}
        />
    );
}
