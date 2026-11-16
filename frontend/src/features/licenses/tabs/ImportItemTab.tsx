import ItemsTab from "@/pages/license-overview/ItemsTab";

/** Import Item tab: the existing overview Items body (`licenses/:id/overview-items/`). */
export default function ImportItemTab({ licenseId }: { licenseId: number }) {
    return <ItemsTab licenseId={licenseId} isActive />;
}
