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
import { fmtNum, pick, pickId, reconKeys, type ReconRow } from "./reconciliationHelpers";

const COLUMNS = ["invoice_number", "company", "invoice_date", "cif_fc", "qty_kg", "licence", "sr_number"];

/**
 * "Missing BOE" — SALE trade lines with no BOE linked at all
 * (`GET /reconciliation/missing-boe/`). Every row action is manual: attach an
 * existing BOE, jump to create a new one, or triage (ignore/mark pending).
 */
export default function MissingBoeTab() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { data, isLoading, isError, error } = useReconTabQuery("missing-boe", "reconciliation/missing-boe/");
    const [linkTarget, setLinkTarget] = useState<ReconRow | null>(null);

    const invalidate = () => {
        queryClient.invalidateQueries({ queryKey: reconKeys.tab("missing-boe") });
        queryClient.invalidateQueries({ queryKey: reconKeys.summary });
    };

    const handleNote = async (row: ReconRow, status: "IGNORED" | "PENDING") => {
        const reason = window.prompt(status === "IGNORED" ? "Reason for ignoring this row:" : "Reason for marking pending:");
        if (reason === null) return;
        try {
            await api.post("reconciliation/note/", {
                status,
                reason,
                trade_id: pickId(row, "trade_id", "id"),
            });
            toast.success(status === "IGNORED" ? "Row ignored." : "Marked as pending.");
            invalidate();
        } catch (err) {
            toast.error((err as { response?: { data?: { message?: string } } })?.response?.data?.message || "Failed to update row.");
        }
    };

    const handleAttach = async (boeId: number | string) => {
        if (!linkTarget) return;
        try {
            await api.post("reconciliation/link/", {
                trade_id: pickId(linkTarget, "trade_id", "id"),
                boe_id: boeId,
            });
            toast.success("BOE attached.");
            invalidate();
        } catch (err) {
            toast.error((err as { response?: { data?: { message?: string } } })?.response?.data?.message || "Failed to attach BOE.");
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
                    invoice_number: (item: ReconRow) => String(pick(item, "invoice_number", "invoice_no") ?? "—"),
                    company: (item: ReconRow) => String(pick(item, "company_name", "counterparty_name", "counterparty", "company") ?? "—"),
                    invoice_date: (item: ReconRow) => {
                        const raw = pick(item, "invoice_date");
                        return raw ? (formatDate(String(raw)) || String(raw)) : "—";
                    },
                    cif_fc: (item: ReconRow) => fmtNum(pick(item, "cif_fc", "total_cif_fc", "cif")),
                    qty_kg: (item: ReconRow) => fmtNum(pick(item, "qty_kg", "total_qty_kg", "qty")),
                    licence: (item: ReconRow) => String(pick(item, "licence_number", "license_number", "licence", "license") ?? "—"),
                    sr_number: (item: ReconRow) => String(pick(item, "sr_number_label", "sr_number_id", "sr_number") ?? "—"),
                }}
                customActions={[
                    {
                        icon: "link-45deg", label: "Attach Existing BOE",
                        onClick: (item: ReconRow) => setLinkTarget(item),
                    },
                    {
                        icon: "plus-circle", label: "Create BOE",
                        onClick: () => navigate("/bill-of-entries/create"),
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
                mode="boe"
                onConfirm={handleAttach}
            />
        </>
    );
}
