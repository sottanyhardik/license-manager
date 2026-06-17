import LicenseExportPanel from "../../components/reports/LicenseExportPanel";

export default function ExpiringLicenses() {
    return (
        <LicenseExportPanel
            title="Expiring Licenses Report"
            description="Export licenses expiring within the specified number of days"
            daysLabel="Days from today"
            defaultDays={30}
            helpText={(days) => `Licenses expiring between today and ${days} days from now`}
            endpoint={(days) => `license/reports/expiring-licenses/?format=excel&days=${days}`}
            filename={(days) => `expiring_licenses_${days}_days.xlsx`}
            features={[
                "Separate sheets for each SION norm",
                "Items grouped by FK with merged serial numbers",
                "Condition notes displayed below items",
                "Item-wise summary per norm",
                "Filtered by purchase status (GE, MI, IP, SM)",
                "Excludes licenses with balance < 100",
            ]}
        />
    );
}
