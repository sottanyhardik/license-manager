import { CheckCircle2, FileText, Layers, Pencil, RefreshCw, Trash2 } from "lucide-react";

import type { ActionMenuItem } from "@/components/shared";
import { saveFilterState } from "@/utils/filterPersistence";

import type { BoeDetailRow, BoeListItem } from "./types";

export interface BoeActionContext {
    canWrite: boolean;
    canTransferLetter: boolean;
    entityName: string;
    filterParams: Record<string, unknown>;
    currentPage: number;
    pageSize: number;
    navigate: (path: string) => void;
    onDelete: (item: BoeListItem) => void;
    onTransferLetter: (id: number) => void;
    onMerge: (item: BoeListItem) => void;
}

/** Confirmed, mutation-backed handlers supplied by `useBoeRowActions`. */
export interface BoeActionHandlers {
    resolveDispute: () => void | Promise<void>;
    updateProductName: () => void | Promise<void>;
}

/** Save the register's filters/pagination, then open the BOE edit page. */
export function persistAndEditBoe(item: BoeListItem, ctx: BoeActionContext): void {
    const { entityName, filterParams, currentPage, pageSize, navigate } = ctx;
    saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
    navigate(`/bill-of-entries/${item.id}/edit`);
}

/**
 * The one action set per expanded BOE (shared ActionMenu, like the Licence
 * card): Edit, Transfer Letter, Merge, Resolve Dispute, Update Product Name,
 * then Delete (danger). Every write action is gated on `canWrite`; the server
 * requires BOE_MANAGER for them. Delete is confirmed by the `onDelete` caller;
 * Resolve Dispute / Update Product Name confirm inside `useBoeRowActions`.
 */
export function buildBoeActionItems(item: BoeListItem, ctx: BoeActionContext, handlers: BoeActionHandlers): ActionMenuItem[] {
    const { canWrite, canTransferLetter, onDelete, onTransferLetter, onMerge } = ctx;
    const hasDispute = ((item.item_details || []) as BoeDetailRow[]).some(r => r.is_dispute);
    const needsProductName = !item.product_name || item.product_name.trim() === '';
    const items: (ActionMenuItem | false)[] = [
        canWrite && { id: 'edit', label: 'Edit', icon: Pencil, onSelect: () => persistAndEditBoe(item, ctx) },
        canTransferLetter && { id: 'transfer-letter', label: 'Transfer Letter', icon: FileText, onSelect: () => onTransferLetter(item.id) },
        canWrite && { id: 'merge', label: 'Merge BOE', icon: Layers, onSelect: () => onMerge(item) },
        canWrite && hasDispute && {
            id: 'resolve-dispute', label: 'Resolve Dispute', icon: CheckCircle2,
            onSelect: () => { void handlers.resolveDispute(); },
        },
        canWrite && needsProductName && {
            id: 'update-product-name', label: 'Update Product Name', icon: RefreshCw,
            onSelect: () => { void handlers.updateProductName(); },
        },
        canWrite && { id: 'delete', label: 'Delete', icon: Trash2, tone: 'danger', onSelect: () => onDelete(item), separatorBefore: true },
    ];
    return items.filter((a): a is ActionMenuItem => Boolean(a));
}
