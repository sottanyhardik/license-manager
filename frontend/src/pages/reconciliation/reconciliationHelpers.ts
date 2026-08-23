import type { ElementType } from "react";
import { Check, Copy, Hourglass, Link2, RefreshCw, ScrollText } from "lucide-react";

/**
 * Shared helpers for the Reconciliation panel (`ReconciliationPanel.tsx` +
 * sibling components in this folder).
 *
 * The backend `apps/reconciliation` app is being built concurrently — every
 * accessor here is written defensively (`??` chains over a few plausible
 * field names) so the UI degrades gracefully rather than crashing if a field
 * name shifts slightly once the real API lands. See the smoke test and the
 * PR description for what was verified against a live backend vs. built
 * strictly to the contract.
 */

// ─── Generic row shape ────────────────────────────────────────────────────
// Deliberately loose — every tab's row shape differs and the exact field
// names are not fully pinned down yet.
export type ReconRow = Record<string, unknown>;

// ─── List response unwrapping ────────────────────────────────────────────
// Mirrors the defensive handling already used by ActivityLog.tsx: some list
// endpoints in this app return a bare array, others `{results, count}`.
export function unwrapList(data: unknown): ReconRow[] {
    if (Array.isArray(data)) return data as ReconRow[];
    if (data && typeof data === "object" && Array.isArray((data as { results?: unknown }).results)) {
        return (data as { results: ReconRow[] }).results;
    }
    return [];
}

// ─── Field pickers (defensive against minor backend naming drift) ───────
export function pick(row: ReconRow, ...keys: string[]): unknown {
    for (const key of keys) {
        const val = row[key];
        if (val !== undefined && val !== null && val !== "") return val;
    }
    return null;
}

export function pickId(row: ReconRow, ...keys: string[]): number | string | null {
    const val = pick(row, ...keys);
    return val === null ? null : (val as number | string);
}

// ─── Number formatting ────────────────────────────────────────────────────
export function fmtNum(value: unknown, maximumFractionDigits = 2): string {
    if (value === null || value === undefined || value === "") return "—";
    const num = Number(value);
    if (Number.isNaN(num)) return "—";
    return num.toLocaleString("en-IN", { maximumFractionDigits });
}

// ─── List-of-labels formatting (e.g. multiple linked BOE/invoice numbers) ─
export function fmtList(value: unknown): string {
    if (value === null || value === undefined) return "—";
    if (Array.isArray(value)) {
        return value.length ? value.join(", ") : "—";
    }
    return String(value) || "—";
}

export function getEntityId(value: unknown): number | string | null {
    if (value && typeof value === "object") {
        return (value as { id?: number | string }).id ?? null;
    }
    return (value as number | string) ?? null;
}

// ─── React Query keys — namespaced so `invalidateQueries(['reconciliation'])`
// invalidates the summary card + every tab in one call. ────────────────────
export const reconKeys = {
    summary: ["reconciliation", "summary"] as const,
    tab: (tab: string) => ["reconciliation", tab] as const,
    auditLog: (scope: string) => ["reconciliation", "audit-log", scope] as const,
};

// ─── Audit log action chip metadata ───────────────────────────────────────
// Modeled on admin/ActivityLog.tsx's ACTION_META pattern. The exact action
// names logged by ReconciliationLog — confirmed from the backend's
// `ACTION_CHOICES` (`backend/apps/reconciliation/models.py`, landed
// concurrently with this frontend work): LINK / MERGE_BOE / IGNORE /
// MARK_PENDING / RECALCULATE. Any unrecognized action still falls back to a
// neutral chip rather than rendering blank, in case a value changes before
// the views/serializers land.
export const RECON_ACTION_META: Record<string, { chipClass: string; Icon: ElementType }> = {
    LINK: { chipClass: "bg-success/10 text-success", Icon: Link2 },
    IGNORE: { chipClass: "bg-muted text-muted-foreground", Icon: Check },
    MARK_PENDING: { chipClass: "bg-warning/10 text-warning", Icon: Hourglass },
    MERGE_BOE: { chipClass: "bg-info/10 text-info", Icon: Copy },
    RECALCULATE: { chipClass: "bg-primary/10 text-primary", Icon: RefreshCw },
};
export const RECON_ACTION_FALLBACK = { chipClass: "bg-muted text-muted-foreground", Icon: ScrollText };

export function reconActionMeta(action: string | null | undefined) {
    if (!action) return RECON_ACTION_FALLBACK;
    return RECON_ACTION_META[action] ?? RECON_ACTION_FALLBACK;
}
