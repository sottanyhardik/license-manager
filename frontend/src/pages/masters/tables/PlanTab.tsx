/**
 * PlanTab — thin wrapper around the shared PlanningEditor core.
 *
 * All planning logic, UI, and business rules live in PlanningEditor so that
 * the tab and the modal (LicensePlanningPanel) are byte-for-byte identical.
 */

import PlanningEditor from "../../../components/planning/PlanningEditor";

interface PlanTabProps {
    licenseId: number;
    licenseNumber: string;
    balanceCif?: number;
    canWrite: boolean;
}

export default function PlanTab({ licenseId, licenseNumber, balanceCif, canWrite }: PlanTabProps) {
    return (
        <PlanningEditor
            licenseId={licenseId}
            licenseNumber={licenseNumber}
            balanceCif={balanceCif}
            canWrite={canWrite}
        />
    );
}
