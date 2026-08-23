import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import DataTable from "@/components/DataTable";
import { formatDate } from "@/utils/dateFormatter";
import { getErrorMessage } from "@/utils/errorUtils";
import LinkRecordModal from "./LinkRecordModal";
import { useReconTabQuery } from "./useReconTabQuery";
import { fmtList, fmtNum, pick, pickId, reconKeys, type ReconRow } from "./reconciliationHelpers";

const COLUMNS = ["bill_of_entry_number", "bill_of_entry_date", "cif_fc", "qty_kg", "licence"];

/**
 * "Missing Invoice" — BOEs with no `invoice_no` at all
 * (`GET /reconciliation/missing-invoice/`), mirroring the "Missing BOE" tab's
 * action set but from the other direction (attach/create a trade invoice).
 */
export default function MissingInvoiceTab() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { data, isLoading, isError, error } = useReconTabQuery("missing-invoice", "reconciliation/missing-invoice/");
    const [linkTarget, setLinkTarget] = useState<ReconRow | null>(null);

    const invalidate = () => {
        queryClient.invalidateQueries({ queryKey: reconKeys.tab("missing-invoice") });
        queryClient.invalidateQueries({ queryKey: reconKeys.summary });
    };

    const handleNote = async (row: ReconRow, status: "IGNORED" | "PENDING") => {
        const reason = window.prompt(status === "IGNORED" ? "Reason for ignoring this row:" : "Reason for marking pending:");
        if (reason === null) return;
        try {
            await api.post("reconciliation/note/", {
                status,
                reason,
                bill_of_entry_id: pickId(row, "boe_id", "bill_of_entry_id", "id"),
            });
            toast.success(status === "IGNORED" ? "Row ignored." : "Marked as pending.");
            invalidate();
        } catch (err) {
            toast.error((err as { response?: { data?: { message?: string } } })?.response?.data?.message || "Failed to update row.");
        }
    };

    const handleAttach = async (tradeId: number | string) => {
        if (!linkTarget) return;
        try {
            await api.post("reconciliation/link/", {
                trade_id: tradeId,
                boe_id: pickId(linkTarget, "boe_id", "bill_of_entry_id", "id"),
            });
            toast.success("Invoice attached.");
            invalidate();
        } catch (err) {
            toast.error((err as { response?: { data?: { message?: string } } })?.response?.data?.message || "Failed to attach invoice.");
        }
    };

    if (isError) {
        return <p className="p-4 text-sm text-destructive">{getErrorMessage(error)}</p>;
    }

    return (
        <>
            <DataTable
                data={data ?? []}
                columns={COLUMNS}
                loading={isLoading}
                customCellRender={{
                    bill_of_entry_number: (item: ReconRow) => String(pick(item, "bill_of_entry_number") ?? "—"),
                    bill_of_entry_date: (item: ReconRow) => {
                        const raw = pick(item, "bill_of_entry_date");
                        return raw ? (formatDate(String(raw)) || String(raw)) : "—";
                    },
                    cif_fc: (item: ReconRow) => fmtNum(pick(item, "total_cif_fc", "cif_fc", "total_cif", "cif")),
                    qty_kg: (item: ReconRow) => fmtNum(pick(item, "total_qty_kg", "qty_kg", "total_quantity", "qty")),
                    licence: (item: ReconRow) => fmtList(pick(item, "licence_numbers", "license_numbers", "licence_number", "license_number")),
                }}
                customActions={[
                    {
                        icon: "link-45deg", label: "Attach Invoice",
                        onClick: (item: ReconRow) => setLinkTarget(item),
                    },
                    {
                        icon: "plus-circle", label: "Create Invoice",
                        onClick: () => navigate("/trades/create"),
                    },
                    {
                        icon: "x-lg", label: "Ignore",
                        onClick: (item: ReconRow) => handleNote(item, "IGNORED"),
                    },
                    {
                        icon: "exclamation-circle", label: "Mark Pending",
                        onClick: (item: ReconRow) => handleNote(item, "PENDING"),
                    },
                ]}
            />
            <LinkRecordModal
                open={linkTarget !== null}
                onOpenChange={(open) => !open && setLinkTarget(null)}
                mode="invoice"
                onConfirm={handleAttach}
            />
        </>
    );
}
