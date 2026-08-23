import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import api from "@/api/axios";
import DataTable from "@/components/DataTable";
import { getErrorMessage } from "@/utils/errorUtils";
import { useReconTabQuery } from "./useReconTabQuery";
import { pick, pickId, reconKeys, type ReconRow } from "./reconciliationHelpers";

const COLUMNS = ["boe_number_a", "boe_number_b", "reason"];

interface DuplicateBoesTabProps {
    // `useConfirmDialog.tsx` is untyped JS, so its inferred return type is
    // `Promise<unknown>` rather than `Promise<boolean>` — widened here to
    // match without touching that shared hook.
    confirmDangerousAction: (title: string, message: string) => Promise<unknown>;
}

/**
 * "Duplicate BOEs (Merge)" — literal duplicate BOE records (same document
 * entered twice), detected separately from the "Duplicate Debits" condition.
 * Merging deletes the source BOE, so it goes through the same
 * `confirmDangerousAction` flow MasterList.tsx already uses for its own
 * "Merge BOE" action, then reuses the existing `merge_boe` service via
 * `POST /reconciliation/merge-boe/`.
 *
 * Which side is "target" (kept) vs "source" (deleted) isn't specified by the
 * contract — this treats BOE A (the first of the pair) as the target and B
 * as the source being merged away; flagged in the PR notes as an assumption
 * to confirm once the backend's exact semantics are visible.
 */
export default function DuplicateBoesTab({ confirmDangerousAction }: DuplicateBoesTabProps) {
    const queryClient = useQueryClient();
    const { data, isLoading, isError, error } = useReconTabQuery("duplicate-boes", "reconciliation/duplicate-boes/");

    const handleMerge = async (row: ReconRow) => {
        const numberA = String(pick(row, "bill_of_entry_number_a", "boe_number_a") ?? "—");
        const numberB = String(pick(row, "bill_of_entry_number_b", "boe_number_b") ?? "—");
        const confirmed = await confirmDangerousAction(
            "Merge Duplicate BOEs",
            `Merge BOE ${numberB} into ${numberA}? This deletes BOE ${numberB} and moves its data onto ${numberA}. This cannot be undone.`,
        );
        if (!confirmed) return;

        try {
            await api.post("reconciliation/merge-boe/", {
                target_boe_id: pickId(row, "boe_id_a"),
                source_boe_id: pickId(row, "boe_id_b"),
            });
            toast.success(`Merged BOE ${numberB} into ${numberA}.`);
            queryClient.invalidateQueries({ queryKey: reconKeys.tab("duplicate-boes") });
            queryClient.invalidateQueries({ queryKey: reconKeys.summary });
        } catch (err) {
            toast.error((err as { response?: { data?: { message?: string } } })?.response?.data?.message || "Failed to merge BOEs.");
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
            customCellRender={{
                boe_number_a: (item: ReconRow) => String(pick(item, "bill_of_entry_number_a", "boe_number_a") ?? "—"),
                boe_number_b: (item: ReconRow) => String(pick(item, "bill_of_entry_number_b", "boe_number_b") ?? "—"),
                reason: (item: ReconRow) => String(pick(item, "reason") ?? "—"),
            }}
            customActions={[
                { icon: "intersect", label: "Merge", onClick: handleMerge },
            ]}
        />
    );
}
