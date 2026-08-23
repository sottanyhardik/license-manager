import { useState } from "react";
import { Link2 } from "lucide-react";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import HybridSelect from "@/components/HybridSelect";

export type LinkRecordMode = "boe" | "invoice";

interface LinkRecordModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    mode: LinkRecordMode;
    /** Called with the id of the record the user picked (a BOE id or a trade id
     *  depending on `mode`). The caller already knows the fixed side of the
     *  link (the row's trade_id / boe_id), so it's threaded in via closure
     *  rather than as a prop here. */
    onConfirm: (selectedId: number | string) => Promise<void> | void;
}

/**
 * Lightweight "Attach Existing BOE/Invoice" modal — reuses the same
 * HybridSelect async-picker pattern TradeForm already uses for its BOE
 * picker (`fieldMeta.endpoint` + `label_field`), wrapped in the shared
 * shadcn Dialog primitive (no new modal component needed).
 */
export default function LinkRecordModal({ open, onOpenChange, mode, onConfirm }: LinkRecordModalProps) {
    const [selectedId, setSelectedId] = useState<number | string | null>(null);
    const [saving, setSaving] = useState(false);

    const isBoe = mode === "boe";
    const title = isBoe ? "Attach Existing BOE" : "Attach Existing Invoice";
    const endpoint = isBoe ? "/bill-of-entries/?available_for_trade=true" : "/trades/";
    const labelField = isBoe ? "bill_of_entry_number" : "invoice_number";
    const placeholder = isBoe ? "Search and select BOE..." : "Search and select trade invoice...";

    const handleClose = (next: boolean) => {
        if (!next) setSelectedId(null);
        onOpenChange(next);
    };

    const handleConfirm = async () => {
        if (selectedId === null) return;
        setSaving(true);
        try {
            await onConfirm(selectedId);
            handleClose(false);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Link2 className="size-4" aria-hidden="true" />
                        {title}
                    </DialogTitle>
                </DialogHeader>

                <div className="py-2">
                    <HybridSelect
                        fieldMeta={{ endpoint, label_field: labelField }}
                        value={selectedId}
                        onChange={(val) => setSelectedId(val as number | string | null)}
                        isClearable
                        placeholder={placeholder}
                    />
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => handleClose(false)} disabled={saving}>
                        Cancel
                    </Button>
                    <Button onClick={handleConfirm} disabled={selectedId === null || saving}>
                        {saving ? "Attaching…" : "Attach"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
