import { toast } from "sonner";

import api from "@/api/axios";
import { saveFilterState } from "@/utils/filterPersistence";

import type { BoeDetailRow, BoeListItem } from "./types";

export interface BoeActionContext {
    canWrite: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: BoeListItem) => void;
    invalidateList: () => void;
    confirmDangerousAction: (title: string, message: string) => Promise<unknown>;
    onTransferLetter: (id: number) => void;
    onMerge: (item: BoeListItem) => void;
}

export interface BoeCardAction {
    icon: string;
    title: string;
    tone?: string;
    onClick: () => void | Promise<void>;
}

type ApiError = { response?: { data?: { detail?: string; message?: string } } };
const errorData = (err: unknown) => (err as ApiError)?.response?.data;

/** Save the register's filters/pagination, then open the BOE edit page. */
export function persistAndEditBoe(item: BoeListItem, ctx: BoeActionContext): void {
    const { entityName, filterParams, currentPage, pageSize, navigate } = ctx;
    saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
    navigate(`/bill-of-entries/${item.id}/edit`);
}

/**
 * The BOE card's actions, moved verbatim out of BoeCardList (same order, icons,
 * tones, endpoints and navigation targets). Every write action is gated on
 * `canWrite`; the server already requires BOE_MANAGER for them.
 */
export function buildBoeActions(item: BoeListItem, ctx: BoeActionContext): BoeCardAction[] {
    const { canWrite, onDelete, invalidateList, confirmDangerousAction, onTransferLetter, onMerge } = ctx;
    const disputeRows = ((item.item_details || []) as BoeDetailRow[]).filter(r => r.is_dispute);
    const hasDispute = disputeRows.length > 0;
    const actions: (BoeCardAction | false)[] = [
        canWrite && hasDispute && {
            icon: 'check2-circle', title: 'Resolve Dispute', tone: 'danger',
            onClick: async () => {
                const confirmed = await confirmDangerousAction('Resolve Dispute', `Resolve ${disputeRows.length} dispute row(s) on BOE ${item.bill_of_entry_number}? This clears the dispute flag on all flagged rows.`);
                if (!confirmed) return;
                try {
                    const response = await api.post(`bill-of-entries/${item.id}/resolve-dispute/`);
                    toast.success(response.data.message || 'Dispute resolved');
                    invalidateList();
                } catch (err) {
                    toast.error(errorData(err)?.detail || errorData(err)?.message || 'Failed to resolve dispute');
                }
            }
        },
        { icon: 'file-earmark-text', title: 'Transfer Letter', tone: 'warning',
            onClick: () => onTransferLetter(item.id) },
        canWrite && { icon: 'intersect', title: 'Merge BOE', tone: 'info',
            onClick: () => onMerge(item) },
        canWrite && (!item.product_name || item.product_name.trim() === '') && {
            icon: 'arrow-repeat', title: 'Update Product Name', tone: 'info',
            onClick: async () => {
                const confirmed = await confirmDangerousAction('Update Product Name', `Update product name for BOE ${item.bill_of_entry_number}?`);
                if (!confirmed) return;
                try {
                    const response = await api.post(`bill-of-entries/${item.id}/update-product-name/`);
                    toast.success(response.data.message || 'Product name updated');
                    invalidateList();
                } catch (err) {
                    toast.error(errorData(err)?.message || 'Failed to update product name');
                }
            }
        },
        canWrite && { icon: 'pencil', title: 'Edit', tone: 'primary',
            onClick: () => persistAndEditBoe(item, ctx) },
        canWrite && { icon: 'trash', title: 'Delete', tone: 'danger', onClick: () => onDelete(item) },
    ];
    return actions.filter((a): a is BoeCardAction => Boolean(a));
}
