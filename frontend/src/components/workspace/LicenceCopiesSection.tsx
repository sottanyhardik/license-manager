import { FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared";
import { OUTLINE_TOKENS } from "@/lib/display";
import { openLicenseCopyPdf } from "@/utils/licenseCopyPdf";

/** Minimal row shape: any record that may carry a licence id and number. */
export interface LicenceCopyRow {
    license_id?: number | null;
    license_number?: string | null;
}

export interface LicenceCopiesSectionProps {
    /** Rows to collect licences from; duplicates (same `license_id`) are shown once, first number wins. */
    rows: readonly LicenceCopyRow[];
    /** Empty-state description shown when no row carries both a licence id and number. */
    emptyDescription: string;
}

/**
 * "Licence copies" section shared by the Allotment and BOE Documents tabs: one
 * button per distinct licence that opens its merged copy PDF
 * (`licenses/:id/merged-documents/`) on click; nothing is requested on render.
 *
 * Accessibility: a labelled `<section aria-label="Licence copies">`; each button
 * has the accessible name "Open License Copy PDF for <number>" and a decorative
 * (`aria-hidden`) icon; the empty state is a `role="status"` region.
 */
export function LicenceCopiesSection({ rows, emptyDescription }: LicenceCopiesSectionProps) {
    const licences = new Map<number, string>();
    rows.forEach((r) => {
        if (r.license_id && r.license_number && !licences.has(r.license_id)) licences.set(r.license_id, r.license_number);
    });
    return (
        <section aria-label="Licence copies">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.06em] text-muted-foreground">Licence copies</h4>
            {licences.size === 0 ? (
                <EmptyState title="No licence documents" description={emptyDescription} />
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
    );
}
