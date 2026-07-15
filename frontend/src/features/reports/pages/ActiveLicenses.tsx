import { LicenseExportPanel } from '../components/LicenseExportPanel'
import { ENDPOINTS } from '@/shared/api/endpoints'

export default function ActiveLicenses() {
  return (
    <LicenseExportPanel
      title="Active Licenses Report"
      description="Export all active licenses from (today − N days) through all future dates"
      daysLabel="Days to look back"
      defaultDays={30}
      helpText={(days) =>
        `Shows licenses with expiry from ${days} days ago through 2026/2027 and beyond`
      }
      endpoint={ENDPOINTS.LICENSES.ACTIVE_LICENSES_REPORT}
      filename={(days) => `active_licenses_${days}_days.xlsx`}
      features={[
        'Separate sheets for each SION norm',
        'Items grouped by FK with merged serial numbers',
        'Condition notes displayed below items',
        'Item-wise summary per norm',
        'Filtered by purchase status (GE, MI, IP, SM)',
        'Excludes licenses with balance < 100',
        'Shows ACTIVE licenses (expiry ≥ today − N days)',
      ]}
    />
  )
}
