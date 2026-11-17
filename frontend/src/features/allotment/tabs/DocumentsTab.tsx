import { LicenceCopiesSection } from "@/components/workspace";
import { ActionButtons } from "./ActionButtons";
import type { AllotmentCardAction, AllotmentDetailRow } from "../types";

type Props = { rows: AllotmentDetailRow[]; actions: AllotmentCardAction[] };

const PDF_ACTIONS = new Set(["Preview PDF", "Download"]);

/**
 * Documents: the allotment PDF (existing `generate-pdf` actions) and each
 * allotted licence's copy (`licenses/:id/merged-documents/`). Nothing is
 * requested until a button is pressed.
 */
export function DocumentsTab({ rows, actions }: Props) {
    return (
        <div className="space-y-4">
            <section aria-label="Allotment PDF">
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Allotment PDF</h4>
                <ActionButtons actions={actions.filter((a) => PDF_ACTIONS.has(a.title))} />
            </section>
            <LicenceCopiesSection rows={rows} emptyDescription="No licences have been allotted yet." />
        </div>
    );
}
