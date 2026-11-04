import { lazy, Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";

// The planning editor is loaded only when the Planning tab opens. It is the existing SION item planner.
const PlanningEditor = lazy(() => import("@/components/planning/PlanningEditor"));

/** The loading region shown while the planning editor module loads. */
export function PlanningTabLoading() {
  return (
    <div role="status" aria-label="Loading planning" className="space-y-2">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

export interface LicencePlanningTabProps {
  licenceId: number;
  licenceNumber: string | null;
  canWrite: boolean;
  /** The licence's canonical available CIF, from the workspace balance. Planning does not calculate a balance. */
  canonicalBalanceCif: number | null;
}

/**
 * The Planning tab. It plans the licence it is given and nothing else. The editor is keyed by the licence
 * ID, so a different licence never shows the previous licence's plan lines.
 */
export default function LicencePlanningTab({ licenceId, licenceNumber, canWrite, canonicalBalanceCif }: LicencePlanningTabProps) {
  return (
    <Suspense
      fallback={<PlanningTabLoading />}
    >
      <PlanningEditor
        key={licenceId}
        licenseId={licenceId}
        licenseNumber={licenceNumber ?? ""}
        canWrite={canWrite}
        canonicalBalanceCif={canonicalBalanceCif}
      />
    </Suspense>
  );
}
