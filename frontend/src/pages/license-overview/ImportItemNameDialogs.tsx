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
import { extractApiError } from "./licenseOverviewHelpers";
import { useImportItemNameHistory } from "./useLicenseImportItemNames";
import type { ImportItemNameItem } from "./types";

const names = (items: ImportItemNameItem[]) => (items.length ? items.map((i) => i.name).join(", ") : "Not Mapped");

interface HistoryProps {
    licenseId: string | number;
    importItemId: number;
    description: string | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function ImportItemNameHistoryDialog({ licenseId, importItemId, description, open, onOpenChange }: HistoryProps) {
    const { data, isLoading, isError, error } = useImportItemNameHistory(licenseId, importItemId, open);
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Item Name history</DialogTitle>
                    <DialogDescription>{description ?? `Import item ${importItemId}`}</DialogDescription>
                </DialogHeader>
                {isLoading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="size-4 animate-spin" /> Loading history…
                    </div>
                )}
                {isError && (
                    <Alert variant="destructive">
                        <AlertDescription>{extractApiError(error, "Failed to load history.")}</AlertDescription>
                    </Alert>
                )}
                {data && data.events.length === 0 && <p className="text-sm text-muted-foreground">No history yet.</p>}
                {data && data.events.length > 0 && (
                    <ul className="max-h-80 space-y-2 overflow-auto text-sm">
                        {data.events.map((ev, idx) => (
                            <li key={`${ev.time}-${idx}`} className="rounded-md border border-border/70 p-2">
                                <div className="flex justify-between gap-2 text-xs text-muted-foreground">
                                    <span className="font-medium text-foreground">{ev.action}</span>
                                    <span>{ev.user ?? "system"} · {ev.time}</span>
                                </div>
                                <div>{names(ev.previous_items)} → {names(ev.new_items)}</div>
                                {ev.note && <div className="text-xs text-muted-foreground">{ev.note}</div>}
                            </li>
                        ))}
                    </ul>
                )}
            </DialogContent>
        </Dialog>
    );
}

interface RevertProps {
    open: boolean;
    description: string | null;
    mappingNames: string;
    busy: boolean;
    onCancel: () => void;
    onConfirm: () => void;
}

export function ImportItemNameRevertDialog({ open, description, mappingNames, busy, onCancel, onConfirm }: RevertProps) {
    return (
        <Dialog open={open} onOpenChange={(o) => { if (!o) onCancel(); }}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Revert to description mapping?</DialogTitle>
                    <DialogDescription>
                        The correction for “{description ?? "this import item"}” is removed and the description mapping
                        ({mappingNames}) applies again.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" onClick={onCancel} disabled={busy}>Cancel</Button>
                    <Button onClick={onConfirm} disabled={busy}>
                        {busy && <Loader2 className="size-4 animate-spin" />} Revert
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
