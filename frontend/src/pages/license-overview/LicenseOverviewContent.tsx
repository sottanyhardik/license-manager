import { useContext } from "react";

import { AuthContext } from "@/context/AuthContext";
import PlanningEditor from "@/components/planning/PlanningEditor";

import OverviewTab from "./OverviewTab";
import ItemsTab from "./ItemsTab";
import { useLicenseOverviewSummary } from "./useLicenseOverviewSummary";

export type LicenseOverviewContentTab = "overview" | "items" | "planning";

/** Shared canonical tab body for full and embedded licence surfaces. */
export default function LicenseOverviewContent({ licenseId, activeTab, mode }: { licenseId: string | number; activeTab: LicenseOverviewContentTab; mode: "full" | "embedded" }) {
    const { hasRole } = useContext(AuthContext);
    const summary = useLicenseOverviewSummary(licenseId, activeTab === "overview" || activeTab === "planning");

    if (activeTab === "planning") {
        return <PlanningEditor licenseId={Number(licenseId)} licenseNumber={summary.data?.license_number || ""} balanceCif={summary.data?.balance_cif ? Number(summary.data.balance_cif) : 0} canWrite={hasRole("LICENSE_MANAGER")} />;
    }

    if (activeTab === "items") {
        return <ItemsTab licenseId={licenseId} isActive />;
    }

    return <div className={mode === "embedded" ? "py-2" : ""}><OverviewTab licenseId={licenseId} isActive showHiddenBoe={false} onShowHiddenBoeChange={() => {}} /></div>;
}
