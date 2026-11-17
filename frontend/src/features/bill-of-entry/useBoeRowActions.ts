import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import type { ActionMenuItem } from "@/components/shared";
import * as boeApi from "@/api/boeApi";
import { extractBoeError } from "@/api/boeApi";
import { invalidateLicence, qk } from "@/lib/queryKeys";

import { buildBoeActionItems, type BoeActionContext } from "./boeCardActions";
import type { BoeDetailRow, BoeListItem } from "./types";

export interface BoeRowActionContext extends BoeActionContext {
    /** Existing register refresh (kept so callers/tests keep a single list-invalidation seam). */
    invalidateList: () => void;
    confirmDangerousAction: (title: string, message: string) => Promise<unknown>;
}

/** Register list, plus any cached BOE record/detail. */
function useInvalidateBoe(invalidateList: () => void) {
    const queryClient = useQueryClient();
    return useCallback(() => {
        invalidateList();
        void queryClient.invalidateQueries({ queryKey: qk.boes.all });
    }, [invalidateList, queryClient]);
}

/**
 * Inline invoice-number edit. Allowed for BOE_MANAGER, BOE_VIEWER and
 * ACCOUNT_ACCESS (D2) - gating is the caller's `canEditInvoice`; the server
 * refuses hidden BOEs (D1) with `{error}`, which is surfaced in the toast.
 */
export function useUpdateBoeInvoiceNo(invalidateList: () => void) {
    const invalidate = useInvalidateBoe(invalidateList);
    return useMutation({
        mutationFn: ({ id, invoiceNo }: { id: number | string; invoiceNo: string }) =>
            boeApi.updateInvoiceNo(id, invoiceNo),
        onSuccess: invalidate,
        onError: (err) => { toast.error(extractBoeError(err, "Failed to update invoice number")); },
    });
}

/** Bulk "Update all empty product names" (whole DB; the caller confirms first). */
export function useBulkUpdateProductNames() {
    return useMutation({ mutationFn: boeApi.bulkUpdateProductNames });
}

/**
 * Per-BOE row actions: typed card descriptors plus the TanStack mutations that
 * back them. Endpoints, payloads and permission gating match iteration 1
 * (canWrite for Resolve/Merge/Update Product Name/Edit/Delete). Hide/restore are
 * licence-hosted and change licence balances, so they also invalidate the
 * licence's cached queries; the other mutations touch only the BOE.
 */
export function useBoeRowActions(item: BoeListItem, ctx: BoeRowActionContext) {
    const { invalidateList, confirmDangerousAction } = ctx;
    const queryClient = useQueryClient();
    const invalidate = useInvalidateBoe(invalidateList);

    const resolveDisputeMutation = useMutation({
        mutationFn: () => boeApi.resolveDispute(item.id),
        onSuccess: (data) => { toast.success(data?.message || "Dispute resolved"); invalidate(); },
        onError: (err) => { toast.error(extractBoeError(err, "Failed to resolve dispute")); },
    });

    const updateProductNameMutation = useMutation({
        mutationFn: () => boeApi.updateProductName(item.id),
        onSuccess: (data) => { toast.success(data?.message || "Product name updated"); invalidate(); },
        onError: (err) => { toast.error(extractBoeError(err, "Failed to update product name")); },
    });

    const hideMutation = useMutation({
        mutationFn: (licenceId: number | string) => boeApi.hideBoe(licenceId, item.id),
        onSuccess: (_d, licenceId) => {
            toast.success("BOE hidden.");
            invalidate();
            void invalidateLicence(queryClient, licenceId);
        },
        onError: (err) => { toast.error(extractBoeError(err, "Failed to hide BOE(s).")); },
    });

    const restoreMutation = useMutation({
        mutationFn: (licenceId: number | string) => boeApi.restoreBoe(licenceId, item.id),
        onSuccess: (_d, licenceId) => {
            toast.success("BOE restored.");
            invalidate();
            void invalidateLicence(queryClient, licenceId);
        },
        onError: (err) => { toast.error(extractBoeError(err, "Failed to restore BOE(s).")); },
    });

    const { mutateAsync: resolveDisputeAsync } = resolveDisputeMutation;
    const { mutateAsync: updateProductNameAsync } = updateProductNameMutation;

    const resolveDispute = useCallback(async () => {
        const rows = ((item.item_details || []) as BoeDetailRow[]).filter(r => r.is_dispute);
        const confirmed = await confirmDangerousAction(
            "Resolve Dispute",
            `Resolve ${rows.length} dispute row(s) on BOE ${item.bill_of_entry_number}? This clears the dispute flag on all flagged rows.`,
        );
        if (!confirmed) return;
        try { await resolveDisputeAsync(); } catch { /* surfaced by onError */ }
    }, [item.item_details, item.bill_of_entry_number, confirmDangerousAction, resolveDisputeAsync]);

    const updateProductName = useCallback(async () => {
        const confirmed = await confirmDangerousAction(
            "Update Product Name",
            `Update product name for BOE ${item.bill_of_entry_number}?`,
        );
        if (!confirmed) return;
        try { await updateProductNameAsync(); } catch { /* surfaced by onError */ }
    }, [item.bill_of_entry_number, confirmDangerousAction, updateProductNameAsync]);

    const actions: ActionMenuItem[] = buildBoeActionItems(item, ctx, { resolveDispute, updateProductName });

    return {
        actions,
        resolveDispute,
        updateProductName,
        hide: hideMutation.mutateAsync,
        restore: restoreMutation.mutateAsync,
        isBusy: resolveDisputeMutation.isPending || updateProductNameMutation.isPending
            || hideMutation.isPending || restoreMutation.isPending,
    };
}
