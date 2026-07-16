import LicenseExportPanel from "../../components/reports/LicenseExportPanel";

export default function ActiveLicenses() {
    return (
        <LicenseExportPanel
            title="Active Licenses Report"
            description="Export all active licenses from today minus the selected lookback period onward"
            daysLabel="Days to look back"
            defaultDays={30}
            helpText={(days) => `Shows licenses expiring from ${days} days ago onward`}
            endpoint={(days) => `license/reports/active-licenses/?format=excel&days=${days}`}
            filename={(days) => `active_licenses_${days}_days.xlsx`}
            features={[
                "Separate sheets for each SION norm",
                "Items grouped by FK with merged serial numbers",
                "Condition notes displayed below items",
                "Item-wise summary per norm",
                "Filtered by purchase status (GE, MI, IP, SM)",
                "Excludes licenses with balance < 100",
                "Shows active licenses expiring from today minus the selected lookback period onward",
            ]}
        />
    );
}
