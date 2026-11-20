import { useEffect, useRef, useState } from "react";
import { History, Loader2, RotateCcw, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ItemNameAsyncSelect } from "@/components/item-async-select";
import { cn } from "@/lib/utils";
import type { ItemNameDraft } from "./importItemNameUtils";
import type { ImportItemNameRow, ImportItemNameScope, ImportItemNameSource } from "./types";

const SOURCE_LABEL: Record<ImportItemNameSource, string> = {
    OVERRIDE: "Override",
    APPROVAL: "Approved mapping",
    DESCRIPTION_MAPPING: "Description mapping",
    AUTO: "Auto",
    OTHER: "Other",
};

interface Props {
    row: ImportItemNameRow | undefined;
    state: "loading" | "error" | "ready";
    canEdit: boolean;
    draft: ItemNameDraft | undefined;
    saving: boolean;
    conflict: boolean;
    /** Description of the row whose global draft this row will follow (same Description + HSN), if any. */
    followsLabel?: string | null;
    /** Whether a global (Description + HSN) decision is possible for this row (blank description: no). */
    canGlobal?: boolean;
    onScope?: (scope: ImportItemNameScope) => void;
    onDraft: (itemId: number | null, label: string | null) => void;
    onRetry: () => void;
    onHistory: () => void;
    onRevert: () => void;
}

/** Item Name cell: display, inline edit (when `canEdit`), and row actions. */
export default function ImportItemNameCell({
    row, state, canEdit, draft, saving, conflict, followsLabel = null, canGlobal = true, onScope, onDraft, onRetry, onHistory, onRevert,
}: Props) {
    const [editing, setEditing] = useState(false);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const wasEditing = useRef(false);

    useEffect(() => {
        if (wasEditing.current && !editing) triggerRef.current?.focus();
        wasEditing.current = editing;
    }, [editing]);

    if (state === "loading") return <span className="text-muted-foreground" aria-label="Loading item name">…</span>;
    if (state === "error" || !row) {
        return (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
                —
                {state === "error" && (
                    <Button type="button" variant="ghost" size="sm" className="h-6 px-1 text-xs" onClick={onRetry} aria-label="Retry loading item names">
                        <RefreshCw className="size-3" /> Retry
                    </Button>
                )}
            </span>
        );
    }

    const currentId = row.items.length === 1 ? row.items[0].id : null;
    const dirty = draft !== undefined;
    const follows = !dirty && followsLabel !== null;
    const shownItems = dirty ? (draft.itemId === null ? [] : [{ id: draft.itemId, name: draft.label ?? `#${draft.itemId}` }]) : row.items;
    const shownName = shownItems.map((i) => i.name).join(", ");
    const status = dirty ? (shownItems.length ? "MAPPED" : "CLEARED") : row.status;
    const label = row.description ?? `import item ${row.import_item_id}`;

    if (editing) {
        return (
            <div
                className="min-w-[220px]"
                onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); setEditing(false); } }}
            >
                <ItemNameAsyncSelect
                    value={dirty ? draft.itemId : currentId}
                    ariaLabel={`Item Name for ${label}`}
                    autoFocus
                    portalMenu
                    onChange={(id, name) => { onDraft(id, name ?? null); setEditing(false); }}
                />
            </div>
        );
    }

    const tooltip =
        status === "MULTIPLE" ? `Multiple (ambiguous): ${shownName}`
        : status === "CONFLICT" ? `Conflict: ${row.note}`
        : status === "CLEARED" ? "Cleared (deliberately no Item Name)"
        : shownName || "Not Mapped";

    let content;
    if (status === "NOT_MAPPED") {
        content = <Badge variant="warning">Not Mapped</Badge>;
    } else if (status === "CLEARED") {
        content = <Badge variant="secondary" title="Deliberately cleared — distinct from Not Mapped">Cleared</Badge>;
    } else if (status === "MULTIPLE") {
        content = <Badge variant="warning" title={shownName}>Multiple (ambiguous)</Badge>;
    } else if (status === "CONFLICT") {
        content = <Badge variant="destructive" title={row.note}>Conflict{row.note ? `: ${row.note}` : ""}</Badge>;
    } else {
        content = <span className="max-w-[200px] truncate">{shownName}</span>;
    }

    const notVerified = !dirty && /not verified/i.test(row.note) && status !== "CONFLICT";

    const approval = row.approval;
    const approvalChip = !dirty && approval && !row.overridden ? (
        <Badge
            variant="success"
            className="text-[10px]"
            title={`Version ${approval.version} · ${approval.records} record${approval.records === 1 ? "" : "s"} on ${approval.licences} licence${approval.licences === 1 ? "" : "s"}${approval.updated_by ? ` · ${approval.updated_by}` : ""}`}
        >
            {approval.status === "USER_APPROVED_CLEAR" ? "Cleared · approved" : "Approved"} v{approval.version}
        </Badge>
    ) : null;

    const body = (
        <>
            {content}
            {dirty && <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400">● Unsaved</span>}
            {notVerified && <span className="text-[10px] text-muted-foreground" title={row.note}>Not verified</span>}
            {approvalChip}
            {!dirty && row.source && !(row.source === "APPROVAL" && approvalChip) && (
                <Badge variant={row.source === "OVERRIDE" ? "info" : "outline"} className="text-[10px]">{SOURCE_LABEL[row.source]}</Badge>
            )}
        </>
    );

    return (
        <div className={cn("flex flex-wrap items-center gap-1.5", dirty && "rounded bg-amber-50 px-1 dark:bg-amber-950/30")}>
            {follows ? (
                <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground" title={`Will follow the change on “${followsLabel}” (same Description + HSN)`}>
                    {body}
                    <Badge variant="info" className="text-[10px]">will follow</Badge>
                </span>
            ) : canEdit ? (
                <button
                    ref={triggerRef}
                    type="button"
                    title={tooltip}
                    aria-label={`Edit Item Name for ${label}`}
                    disabled={saving}
                    onClick={() => setEditing(true)}
                    className="flex min-w-0 items-center gap-1.5 rounded px-1 py-0.5 text-left outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40"
                >
                    {body}
                </button>
            ) : (
                <span className="flex min-w-0 items-center gap-1.5" title={tooltip}>{body}</span>
            )}
            {saving && <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground"><Loader2 className="size-3 animate-spin" /> Saving…</span>}
            {dirty && canEdit && onScope && (
                <div role="group" aria-label={`Scope for ${label}`} className="flex items-center gap-0.5 text-[10px]">
                    {([["global", "All matching records", "Applies to every import item on every licence with the same Description + HSN"],
                        ["record", "This record only", "Keeps an exception for this import item only (beats the global decision)"]] as const).map(([value, text, hint]) => {
                        const pressed = draft.scope === value;
                        return (
                            <button
                                key={value}
                                type="button"
                                aria-pressed={pressed}
                                title={hint}
                                disabled={saving || (value === "global" && !canGlobal)}
                                onClick={() => onScope(value)}
                                className={cn(
                                    "rounded border px-1.5 py-0.5 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:opacity-50",
                                    pressed ? "border-primary bg-primary/10 font-semibold text-primary" : "border-border text-muted-foreground hover:bg-muted",
                                )}
                            >
                                {text}
                            </button>
                        );
                    })}
                </div>
            )}
            {conflict && <span className="text-[10px] font-semibold text-destructive">Changed by someone else</span>}
            <Button type="button" variant="ghost" size="icon" className="size-6" onClick={onHistory} aria-label={`Item Name history for ${label}`} title="History">
                <History className="size-3.5" />
            </Button>
            {canEdit && row.overridden && row.description_mapping && !dirty && (
                <Button type="button" variant="ghost" size="icon" className="size-6" onClick={onRevert} aria-label={`Revert to description mapping for ${label}`} title="Revert to description mapping">
                    <RotateCcw className="size-3.5" />
                </Button>
            )}
        </div>
    );
}
