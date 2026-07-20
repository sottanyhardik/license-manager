/**
 * LicensePlanningPanel — Dialog wrapper around the shared PlanningEditor core.
 *
 * The planning UI rendered inside is byte-for-byte identical to the PlanTab:
 * same components, same business logic, same inline-edit per-row pattern.
 * This file only adds the Dialog chrome (open/close) and routes the onSaved
 * callback back to the caller (report refresh, list refresh, etc.).
 *
 * Props (unchanged — backward-compatible with all existing callers):
 *   show        — controls Dialog visibility
 *   onHide      — called when user dismisses the dialog (✕ or overlay click)
 *   licenseId   — which license to plan
 *   licenseNumber — display label
 *   balanceCif  — seed value (overridden by fresh API data on load)
 *   onSaved     — called after each per-row save so the parent can refresh
 */

import { Dialog, DialogContent } from "@/components/ui/dialog";
import PlanningEditor from "./PlanningEditor";

interface LicensePlanningPanelProps {
    show: boolean;
    onHide: () => void;
    licenseId: number;
    licenseNumber: string;
    balanceCif?: number;
    onSaved?: () => void;
}

export default function LicensePlanningPanel({
    show,
    onHide,
    licenseId,
    licenseNumber,
    balanceCif = 0,
    onSaved,
}: LicensePlanningPanelProps) {
    if (!licenseId) return null;

    return (
        <Dialog open={show} onOpenChange={(open) => { if (!open) onHide?.(); }}>
            {/* max-w-4xl keeps the wide pivot-table layout; overflow-y-auto
                lets PlanningEditor scroll inside the dialog on small screens. */}
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                <PlanningEditor
                    licenseId={licenseId}
                    licenseNumber={licenseNumber}
                    balanceCif={balanceCif}
                    canWrite={true}
                    onSaved={onSaved}
                />
            </DialogContent>
        </Dialog>
    );
}
