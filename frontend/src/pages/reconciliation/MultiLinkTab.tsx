import { useNavigate } from "react-router-dom";

import DataTable from "@/components/DataTable";
import { getErrorMessage } from "@/utils/errorUtils";
import { useReconTabQuery } from "./useReconTabQuery";
import { fmtList, pick, pickId, type ReconRow } from "./reconciliationHelpers";

interface MultiLinkTabProps {
    /** "boe" = "Multiple BOEs" (one invoice, several BOEs); "invoice" = "Multiple Invoices" (one BOE, several trades). */
    kind: "boe" | "invoice";
}

/**
 * Shared read-only table for "Multiple BOEs" and "Multiple Invoices" — both
 * are simple group-by-count views over the existing trade<->BOE M2M, no
 * write actions, just a "view through" link to the anchor record.
 */
export default function MultiLinkTab({ kind }: MultiLinkTabProps) {
    const navigate = useNavigate();
    const isBoe = kind === "boe";
    const tabKey = isBoe ? "multi-boe" : "multi-invoice";
    const { data, isLoading, isError, error } = useReconTabQuery(tabKey, `reconciliation/${tabKey}/`);

    const columns = isBoe
        ? ["invoice_number", "boe_numbers"]
        : ["bill_of_entry_number", "invoice_numbers"];

    if (isError) {
        return <p className="p-4 text-sm text-destructive">{getErrorMessage(error)}</p>;
    }

    return (
        <DataTable
            data={data ?? []}
            columns={columns}
            loading={isLoading}
            customCellRender={isBoe ? {
                invoice_number: (item: ReconRow) => String(pick(item, "invoice_number") ?? "—"),
                boe_numbers: (item: ReconRow) => fmtList(pick(item, "boe_numbers", "linked_boe_numbers", "bill_of_entry_numbers")),
            } : {
                bill_of_entry_number: (item: ReconRow) => String(pick(item, "bill_of_entry_number") ?? "—"),
                invoice_numbers: (item: ReconRow) => fmtList(pick(item, "invoice_numbers", "linked_invoice_numbers", "trade_invoice_numbers")),
            }}
            customActions={[
                isBoe ? {
                    icon: "Eye", label: "View Trade",
                    showIf: (item: ReconRow) => pickId(item, "trade_id") !== null,
                    onClick: (item: ReconRow) => navigate(`/trades/${pickId(item, "trade_id")}/edit`),
                } : {
                    icon: "Eye", label: "View BOE",
                    showIf: (item: ReconRow) => pickId(item, "boe_id") !== null,
                    onClick: (item: ReconRow) => navigate(`/bill-of-entries/${pickId(item, "boe_id")}/edit`),
                },
            ]}
        />
    );
}
