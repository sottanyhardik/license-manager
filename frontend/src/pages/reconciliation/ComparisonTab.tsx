import { useNavigate } from "react-router-dom";

import DataTable from "@/components/DataTable";
import { getErrorMessage } from "@/utils/errorUtils";
import { useReconTabQuery } from "./useReconTabQuery";
import { fmtList, fmtNum, pick, pickId, type ReconRow } from "./reconciliationHelpers";

interface ComparisonTabProps {
    /** "cif" or "qty" — selects which field family + tab endpoint to read. */
    kind: "cif" | "qty";
}

/**
 * Shared read-only table for the "CIF Comparison" and "Quantity Comparison"
 * tabs — same row shape (trade + linked BOEs + two-sided total + a
 * difference), just a different metric. No write actions per the brief;
 * only a trivial "view trade" navigate-through.
 */
export default function ComparisonTab({ kind }: ComparisonTabProps) {
    const navigate = useNavigate();
    const tabKey = kind === "cif" ? "cif-comparison" : "qty-comparison";
    const { data, isLoading, isError, error } = useReconTabQuery(tabKey, `reconciliation/${tabKey}/`);

    // Backend's `_linked_trade_comparison` returns generic `invoice_total`/
    // `boe_total` for both CIF and quantity (see
    // `backend/apps/reconciliation/services/queries.py`) — check that first,
    // with kind-specific names as a fallback in case that shifts.
    const invoiceKeys = kind === "cif"
        ? ["invoice_total", "invoice_cif", "invoice_cif_fc", "trade_cif"]
        : ["invoice_total", "invoice_qty", "invoice_qty_kg", "trade_qty"];
    const boeKeys = kind === "cif"
        ? ["boe_total", "boe_cif", "boe_cif_fc"]
        : ["boe_total", "boe_qty", "boe_qty_kg"];

    const columns = ["invoice_number", "boe_numbers", `invoice_${kind}`, `boe_${kind}`, "difference"];

    if (isError) {
        return <p className="p-4 text-sm text-destructive">{getErrorMessage(error)}</p>;
    }

    return (
        <DataTable
            data={data ?? []}
            columns={columns}
            loading={isLoading}
            getRowStyle={(item: ReconRow) => {
                const diff = Number(pick(item, "difference") ?? 0);
                return !Number.isNaN(diff) && diff !== 0
                    ? { backgroundColor: "var(--tb-warning-soft)", boxShadow: "inset 3px 0 0 var(--tb-warning)" }
                    : undefined;
            }}
            customCellRender={{
                invoice_number: (item: ReconRow) => String(pick(item, "invoice_number") ?? "—"),
                boe_numbers: (item: ReconRow) => fmtList(pick(item, "boe_numbers", "linked_boe_numbers", "bill_of_entry_numbers")),
                [`invoice_${kind}`]: (item: ReconRow) => fmtNum(pick(item, ...invoiceKeys)),
                [`boe_${kind}`]: (item: ReconRow) => fmtNum(pick(item, ...boeKeys)),
                difference: (item: ReconRow) => fmtNum(pick(item, "difference")),
            }}
            customActions={[
                {
                    icon: "Eye", label: "View Trade",
                    showIf: (item: ReconRow) => pickId(item, "trade_id") !== null,
                    onClick: (item: ReconRow) => navigate(`/trades/${pickId(item, "trade_id")}/edit`),
                },
            ]}
        />
    );
}
