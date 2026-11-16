import { ModuleAccordion } from "@/components/workspace";
import BoesTab from "@/pages/license-overview/BoesTab";
import AllotmentsTab from "@/pages/license-overview/AllotmentsTab";

/**
 * BOE & Allotment tab: the existing overview BOE and Allotments bodies
 * (`overview-boes/`, `overview-allotments/`) as two accordion sections.
 * Each body mounts (and fetches) only while its section is open.
 */
export default function BoeAllotmentTab({ licenseId }: { licenseId: number }) {
    return (
        <ModuleAccordion
            persistKey={`license:${licenseId}:boe-allotment`}
            sections={[
                { id: "boes", title: "Bills of Entry", defaultOpen: true, render: () => <BoesTab licenseId={licenseId} isActive /> },
                { id: "allotments", title: "Allotments", defaultOpen: true, render: () => <AllotmentsTab licenseId={licenseId} isActive /> },
            ]}
        />
    );
}
