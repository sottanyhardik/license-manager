import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import DataTable from "@/components/DataTable";
import { getErrorMessage } from "@/utils/errorUtils";
import { useReconTabQuery } from "./useReconTabQuery";
import { fmtNum, pick, pickId, reconKeys, type ReconRow } from "./reconciliationHelpers";

const COLUMNS = ["sr_number", "licence", "invoice_number", "bill_of_entry_number", "invoice_debit", "boe_debit", "difference"];

const DISABLED_ACTION_CLASS =
    "inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-muted-foreground/40 opacity-60 pointer-events-none cursor-not-allowed";

function isMismatched(row: ReconRow): boolean {
    const diff = Number(pick(row, "difference") ?? 0);
    return !Number.isNaN(diff) && diff !== 0;
}

/**
 * "Duplicate Debits" — the literal double-debit condition this whole panel
 * exists to surface (a SALE trade-line debit *and* a BOE row debit for the
 * same sr_number, with the BOE not linked to that trade). Only "Keep Invoice
 * Debit" is wired live in this pass — it's the same "attach the BOE" action
 * that suppresses the duplicate once the calculator's line-level exclusion
 * fix lands. "Keep BOE Debit" / "Undo" need a per-line exclude-from-balance
 * mechanism that doesn't exist yet (Phase 2 per the reconciliation plan), so
 * they render disabled with an explanatory tooltip rather than promising
 * unbuilt behavior.
 */
export default function DuplicateDebitsTab() {
    const queryClient = useQueryClient();
    const { data, isLoading, isError, error } = useReconTabQuery("duplicate-debits", "reconciliation/duplicate-debits/");

    const handleKeepInvoiceDebit = async (row: ReconRow) => {
        try {
            await api.post("reconciliation/link/", {
                trade_id: pickId(row, "trade_id"),
                boe_id: pickId(row, "boe_id"),
            });
            toast.success("BOE linked — invoice debit kept.");
            queryClient.invalidateQueries({ queryKey: reconKeys.tab("duplicate-debits") });
            queryClient.invalidateQueries({ queryKey: reconKeys.summary });
        } catch (err) {
            toast.error((err as { response?: { data?: { message?: string } } })?.response?.data?.message || "Failed to link BOE.");
        }
    };

    if (isError) {
        return <p className="p-4 text-sm text-destructive">{getErrorMessage(error)}</p>;
    }

    return (
        <DataTable
            data={data ?? []}
            columns={COLUMNS}
            loading={isLoading}
            getRowStyle={(item: ReconRow) =>
                isMismatched(item) ? { backgroundColor: "var(--tb-danger-soft)", boxShadow: "inset 3px 0 0 var(--tb-danger)" } : undefined
            }
            customCellRender={{
                sr_number: (item: ReconRow) => String(pick(item, "sr_number_id", "sr_number") ?? "—"),
                licence: (item: ReconRow) => String(pick(item, "licence_number", "license_number", "licence", "license") ?? "—"),
                invoice_number: (item: ReconRow) => String(pick(item, "invoice_number") ?? "—"),
                bill_of_entry_number: (item: ReconRow) => String(pick(item, "bill_of_entry_number") ?? "—"),
                invoice_debit: (item: ReconRow) => fmtNum(pick(item, "invoice_debit")),
                boe_debit: (item: ReconRow) => fmtNum(pick(item, "boe_debit")),
                difference: (item: ReconRow) => fmtNum(pick(item, "difference")),
            }}
            customActions={[
                {
                    icon: "check2-circle", label: "Keep Invoice Debit",
                    onClick: handleKeepInvoiceDebit,
                },
                {
                    icon: "arrow-left-right", label: "Not yet available",
                    className: DISABLED_ACTION_CLASS,
                    onClick: () => {},
                },
                {
                    icon: "arrow-repeat", label: "Not yet available",
                    className: DISABLED_ACTION_CLASS,
                    onClick: () => {},
                },
            ]}
        />
    );
}
