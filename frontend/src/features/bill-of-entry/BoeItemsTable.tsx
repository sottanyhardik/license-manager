import { TriangleAlert } from "lucide-react";

import DetailTable from "@/components/primitives/DetailTable";
import { cn } from "@/lib/utils";
import { openLicenseCopyPdf } from "@/utils/licenseCopyPdf";

import { fmtFc2, fmtInr, fmtQty } from "./format";
import type { BoeDetailRow } from "./types";

/**
 * The BOE item table, moved unchanged from the card's former expanded body
 * (columns, formatting, dispute styling and licence-copy buttons are identical).
 */
export function BoeItemsTable({ rows }: { rows: BoeDetailRow[] }) {
    return (
        <DetailTable
            columns={[
                { key: 'is_dispute', label: '', nowrap: true, width: 28,
                    render: (v, row) => row.is_dispute
                        ? <span title="Not found in latest ledger upload — dispute" className="text-destructive text-sm"><TriangleAlert className="size-4" aria-hidden="true" /></span>
                        : null },
                { key: 'license_number',   label: 'License',   bold: true, nowrap: true,
                    render: (v, row) => v && row.license_id ? (
                        <button
                            type="button"
                            onClick={() => openLicenseCopyPdf(row.license_id, v)}
                            className={cn(row.is_dispute ? 'text-destructive' : 'text-primary', 'hover:underline underline-offset-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring', 'cursor-pointer')}
                            title="Open License Copy PDF"
                            aria-label={`Open License Copy PDF for ${v}`}
                        >
                            {v}
                        </button>
                    ) : (
                        <span className={cn(row.is_dispute ? 'text-destructive' : 'text-primary')}>{v || '—'}</span>
                    ) },
                { key: 'item_description', label: 'Item',      muted: true },
                { key: 'hs_code',          label: 'HS Code',   nowrap: true,
                    render: v => v ? <code>{v}</code> : '—' },
                { key: 'qty',              label: 'Qty',       align: 'right', nowrap: true,
                    render: v => fmtQty(v) },
                { key: 'cif_fc',           label: 'CIF (FC)',  align: 'right', nowrap: true,
                    render: v => fmtFc2(v) },
                { key: 'cif_inr',          label: 'CIF (INR)', align: 'right', nowrap: true, bold: true,
                    render: v => fmtInr(v) },
            ]}
            rows={rows}
            rowStyle={row => row.is_dispute ? { background: 'var(--tb-danger-soft)' } : undefined}
        />
    );
}
