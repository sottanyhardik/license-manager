import {
    BarChart3, CloudDownload, FileSpreadsheet, FileText, Pencil, RefreshCw, Scale, Target, Trash2,
} from "lucide-react";

import type { ActionMenuItem } from "@/components/shared";

export interface LicenceActionHandlers {
    openOverview: () => void;
    editLicence: () => void;
    autoPlan: () => void;
    fetchFromDgft: () => void;
    downloadPdf: () => void;
    downloadExcel: () => void;
    deleteLicence: () => void;
}

interface BuildArgs extends LicenceActionHandlers {
    canWrite: boolean;
    isPlanning: boolean;
    isFetchingDGFT: boolean;
}

/**
 * The one action set per expanded licence, grouped primary / secondary /
 * destructive. Same handlers and `canWrite` gating as the former ActionPanel
 * and Edit Options tab. Delete keeps its existing confirmation (owned by the
 * `onDelete` caller), so no extra confirm is added here.
 */
export function buildLicenceActionItems(a: BuildArgs): ActionMenuItem[] {
    const items: ActionMenuItem[] = [
        { id: "overview", label: "License Overview", icon: BarChart3, onSelect: a.openOverview },
    ];
    if (a.canWrite) {
        items.push(
            { id: "edit", label: "Edit", icon: Pencil, onSelect: a.editLicence, separatorBefore: true },
            {
                id: "auto-plan",
                label: a.isPlanning ? "Planning…" : "Auto Plan",
                icon: a.isPlanning ? RefreshCw : Target,
                onSelect: a.autoPlan,
                disabled: a.isPlanning,
            },
            {
                id: "fetch-dgft",
                label: a.isFetchingDGFT ? "Fetching…" : "Fetch from DGFT",
                icon: a.isFetchingDGFT ? RefreshCw : CloudDownload,
                onSelect: a.fetchFromDgft,
                disabled: a.isFetchingDGFT,
            },
        );
    }
    items.push(
        { id: "balance-pdf", label: "Balance PDF", icon: FileText, onSelect: a.downloadPdf, separatorBefore: !a.canWrite },
        { id: "balance-excel", label: "Balance Excel", icon: FileSpreadsheet, onSelect: a.downloadExcel },
    );
    if (a.canWrite) {
        items.push(
            { id: "recalculate-link", label: "Recalculate / hide-restore BOE (License Overview)", icon: Scale, onSelect: a.openOverview },
            { id: "delete", label: "Delete", icon: Trash2, tone: "danger", onSelect: a.deleteLicence, separatorBefore: true },
        );
    }
    return items;
}
