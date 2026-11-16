import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared";
import { openLicenseCopyPdf } from "@/utils/licenseCopyPdf";
import { OUTLINE_TOKENS } from "@/lib/display";
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
    const licences = new Map<number, string>();
    rows.forEach((r) => {
        if (r.license_id && r.license_number && !licences.has(r.license_id)) licences.set(r.license_id, r.license_number);
    });
    return (
        <div className="space-y-4">
            <section aria-label="Allotment PDF">
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Allotment PDF</h4>
                <ActionButtons actions={actions.filter((a) => PDF_ACTIONS.has(a.title))} />
            </section>
            <section aria-label="Licence copies">
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Licence copies</h4>
                {licences.size === 0 ? (
                    <EmptyState title="No licence documents" description="No licences have been allotted yet." />
                ) : (
                    <div className="flex flex-wrap gap-2">
                        {[...licences].map(([licenseId, licenseNumber]) => (
                            <Button
                                key={licenseId}
                                type="button"
                                size="sm"
                                variant="outline"
                                className={OUTLINE_TOKENS}
                                onClick={() => { void openLicenseCopyPdf(licenseId, licenseNumber); }}
                                aria-label={`Open License Copy PDF for ${licenseNumber}`}
                            >
                                <FileText aria-hidden="true" />
                                {licenseNumber}
                            </Button>
                        ))}
                    </div>
                )}
            </section>
        </div>
    );
}
