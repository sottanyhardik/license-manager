import { FileText } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { LicenceCopiesSection } from "@/components/workspace";
import { openDocument } from "@/utils/documentDownload";

import { OUTLINE_TOKENS } from "@/lib/display";
import type { BoeDetailRow } from "../types";

type Props = {
    boeNumber?: string | null;
    boePdfCopy?: string | null;
    rows: BoeDetailRow[];
    onTransferLetter: () => void;
};

/**
 * Documents: the stored BOE copy (`boe_pdf_copy`, opened like the edit page does),
 * the existing transfer-letter modal, and each licence's copy. Nothing is
 * requested until a button is pressed.
 */
export function DocumentsTab({ boeNumber, boePdfCopy, rows, onTransferLetter }: Props) {
    const openCopy = () => {
        if (!boePdfCopy) return;
        openDocument(boePdfCopy).catch(() => toast.error("Failed to open BOE copy"));
    };
    return (
        <div className="space-y-4">
            <section aria-label="BOE documents">
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">BOE</h4>
                <div className="flex flex-wrap gap-2">
                    {boePdfCopy ? (
                        <Button type="button" size="sm" variant="outline" className={OUTLINE_TOKENS} onClick={openCopy}>
                            <FileText aria-hidden="true" />
                            BOE copy PDF{boeNumber ? ` (${boeNumber})` : ""}
                        </Button>
                    ) : (
                        <span className="self-center text-sm text-muted-foreground">No BOE copy uploaded.</span>
                    )}
                    <Button type="button" size="sm" variant="outline" className={OUTLINE_TOKENS} onClick={onTransferLetter}>
                        <FileText aria-hidden="true" />
                        Transfer Letter
                    </Button>
                </div>
            </section>
            <LicenceCopiesSection rows={rows} emptyDescription="No licence rows are mapped to this BOE." />
        </div>
    );
}
