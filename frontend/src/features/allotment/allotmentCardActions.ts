import { toast } from "sonner";
import { ArrowDownToLine, Copy, Download, FileText, Pencil, Trash2, type LucideIcon } from "lucide-react";
import type { ActionMenuItem } from "@/components/shared";
import api from "@/api/axios";
import { openPdfPreview } from "@/utils/pdfPreview";
import { saveFilterState } from "@/utils/filterPersistence";
import type { AllotmentActionContext, AllotmentCardAction, AllotmentRecord } from "./types";

type ApiError = { response?: { data?: { error?: string } } };
const errorText = (err: unknown, fallback: string) => (err as ApiError)?.response?.data?.error || fallback;

/**
 * The allotment card's actions, moved verbatim out of AllotmentsTable so the
 * card header and the record workspace's Edit Options tab share one source
 * (same order, icons, tones, role gating, endpoints and navigation targets).
 */
export function buildAllotmentActions(item: AllotmentRecord, ctx: AllotmentActionContext): AllotmentCardAction[] {
    const { canWrite, entityName, filterParams, currentPage, pageSize, navigate, onDelete } = ctx;
    const persist = () => saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
    const actions: (AllotmentCardAction | false)[] = [
        canWrite && { icon: 'pencil', title: 'Edit', tone: 'primary',
            onClick: () => { persist(); navigate(`/allotments/${item.id}/edit`); } },
        canWrite && { icon: 'copy', title: 'Copy', tone: 'info',
            onClick: async () => {
                if (!window.confirm(`Create a copy of allotment ${item.invoice || 'this allotment'}?`)) return;
                try {
                    const r = await api.post(`allotments/${item.id}/copy/`);
                    toast.success('Allotment copied. Opening in edit mode...');
                    persist();
                    navigate(`/allotments/${r.data.id}/edit`);
                } catch (err) { toast.error(errorText(err, 'Failed to copy')); }
            } },
        canWrite && { icon: 'box-arrow-in-down', title: 'Allocate', tone: 'success',
            onClick: () => { persist(); navigate(`/allotments/${item.id}/allocate`); } },
        { icon: 'file-pdf', title: 'Preview PDF', tone: 'warning',
            onClick: async () => {
                try {
                    const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                    openPdfPreview(r.data, `${item.invoice_number || item.id}.pdf`);
                } catch (err) { toast.error(errorText(err, 'Failed to generate PDF')); }
            } },
        { icon: 'download', title: 'Download',
            onClick: async () => {
                try {
                    const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                    const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `Allotment-${item.invoice || item.id}.pdf`;
                    document.body.appendChild(a); a.click(); a.remove();
                    setTimeout(() => window.URL.revokeObjectURL(url), 10000);
                } catch (err) { toast.error(errorText(err, 'Failed to download PDF')); }
            } },
        canWrite && { icon: 'trash', title: 'Delete', tone: 'danger', onClick: () => onDelete(item) },
    ];
    return actions.filter((a): a is AllotmentCardAction => Boolean(a));
}

export const ALLOTMENT_ACTION_ICONS: Record<string, LucideIcon> = {
    pencil: Pencil,
    copy: Copy,
    "box-arrow-in-down": ArrowDownToLine,
    "file-pdf": FileText,
    download: Download,
    trash: Trash2,
};

/**
 * The same actions as compact action-menu items (row action menu). `overrides`
 * replaces a handler by title — e.g. Edit opens the inline Edit tab instead of
 * the edit page. Order, gating and tones are unchanged.
 */
export function toActionMenuItems(actions: AllotmentCardAction[], overrides: Record<string, () => void> = {}): ActionMenuItem[] {
    return actions.map((a) => ({
        id: a.title.toLowerCase().replace(/\s+/g, "-"),
        label: a.title,
        icon: ALLOTMENT_ACTION_ICONS[a.icon],
        tone: a.tone === "danger" ? "danger" as const : "default" as const,
        separatorBefore: a.tone === "danger",
        onSelect: overrides[a.title] ?? (() => { void a.onClick(); }),
    }));
}
