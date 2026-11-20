import { Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import type { ImportItemNamePreview } from "./types";

export interface GlobalDraftSummary {
    importItemId: number;
    /** New Item Name, or null for "Clear". */
    itemName: string | null;
}

interface Props {
    open: boolean;
    drafts: GlobalDraftSummary[];
    recordOnlyCount: number;
    previews: ImportItemNamePreview[] | undefined;
    loading: boolean;
    error: string | null;
    saving: boolean;
    onRetry: () => void;
    onCancel: () => void;
    onConfirm: () => void;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Confirmation for "Save all": shows exactly what each global (Description + HSN) decision will touch. */
export default function ImportItemNameSaveDialog({
    open, drafts, recordOnlyCount, previews, loading, error, saving, onRetry, onCancel, onConfirm,
}: Props) {
    const byId = new Map((previews ?? []).map((p) => [p.import_item_id, p]));
    const ready = !loading && !error && !!previews;
    return (
        <Dialog open={open} onOpenChange={(o) => { if (!o && !saving) onCancel(); }}>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Confirm Item Name changes</DialogTitle>
                    <DialogDescription>
                        {plural(drafts.length, "global decision")} will apply to every import item with the same Description + HSN, on every licence.
                        {recordOnlyCount > 0 && ` ${plural(recordOnlyCount, "record-only change")} will also be saved.`}
                    </DialogDescription>
                </DialogHeader>
                {loading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                        <Loader2 className="size-4 animate-spin" /> Checking affected records…
                    </div>
                )}
                {error && (
                    <Alert variant="destructive">
                        <AlertDescription className="flex flex-wrap items-center gap-2">
                            <span>{error}</span>
                            <Button type="button" size="sm" variant="outline" onClick={onRetry}>Retry</Button>
                        </AlertDescription>
                    </Alert>
                )}
                {ready && (
                    <ul className="max-h-[50vh] space-y-2 overflow-auto text-sm" aria-label="Affected combinations">
                        {drafts.map((d) => {
                            const p = byId.get(d.importItemId);
                            if (!p) return null;
                            const dist = Object.entries(p.current_item_sets);
                            return (
                                <li key={d.importItemId} className="space-y-1 rounded-md border border-border/70 p-2">
                                    <div className="truncate font-medium" title={p.combination.description}>{p.combination.description}</div>
                                    <div className="text-xs text-muted-foreground">HSN: {p.combination.hsn_code || "No HSN"}</div>
                                    <div>New Item Name: <strong>{d.itemName ?? "Clear (no Item Name)"}</strong></div>
                                    <div className="text-xs">
                                        <strong>{plural(p.records, "record")}</strong> on <strong>{plural(p.licences, "licence")}</strong>
                                        {p.overridden > 0 && <> · <strong>{p.overridden} overridden</strong> (skipped)</>}
                                    </div>
                                    {p.licence_numbers.length > 0 && (
                                        <div className="break-words text-xs text-muted-foreground">Licences: {p.licence_numbers.join(", ")}</div>
                                    )}
                                    {dist.length > 0 && (
                                        <div className="text-xs text-muted-foreground">
                                            Currently: {dist.map(([name, n]) => `${name || "Not Mapped"} × ${n}`).join(", ")}
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                )}
                <DialogFooter>
                    <Button variant="outline" onClick={onCancel} disabled={saving}>Cancel</Button>
                    <Button onClick={onConfirm} disabled={!ready || saving}>
                        {saving && <Loader2 className="size-4 animate-spin" />} Save changes
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
