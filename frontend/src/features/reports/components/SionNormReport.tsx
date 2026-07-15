import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { Card, CardContent } from '@/shared/ui/card'
import { formatDate } from '@/shared/utils/formatters'

// ── Types ─────────────────────────────────────────────────────────────────────

export type SionNorm = 'E1' | 'E5' | 'E126' | 'E132'

interface VegetableOil {
  hsn_code?: string
  description?: string
  total_qty?: number
  rbd_qty?: number
  rbd_cif?: number
  pko_qty?: number
  pko_cif?: number
  olive_qty?: number
  olive_cif?: number
}

interface Juice {
  hsn_code?: string
  description?: string
  qty?: number
  cif?: number
}

interface FoodFlavour {
  hsn_code?: string
  description?: string
  ff_qty?: number
  df_qty?: number
}

interface FruitCocoa {
  qty?: number
  cif?: number
}

interface LeaveningAgent {
  qty?: number
}

interface Starch1108 {
  qty?: number
  cif?: number
}

interface Starch3505 {
  qty?: number
}

interface MilkAndMilk {
  description?: string
  total_qty?: number
  cheese_qty?: number
  cheese_cif?: number
  swp_qty?: number
  swp_cif?: number
  wpc_qty?: number
  wpc_cif?: number
}

interface PP {
  hsn_code?: string
  description?: string
  qty?: number
}

interface AluminiumFoil {
  qty?: number
}

interface LicenseRow {
  id: number
  license_number: string
  license_date?: string
  license_expiry_date?: string
  exporter_name?: string
  total_cif?: number
  balance_cif?: number
  vegetable_oil?: VegetableOil
  ten_percent_balance?: number
  juice?: Juice
  food_flavour?: FoodFlavour
  fruit_cocoa?: FruitCocoa
  leavening_agent?: LeaveningAgent
  starch_1108?: Starch1108
  starch_3505?: Starch3505
  milk_and_milk?: MilkAndMilk
  pp?: PP
  aluminium_foil?: AluminiumFoil
  wastage_cif?: number
}

interface NotifTotals {
  total_cif?: number
  balance_cif?: number
  veg_oil_total_qty?: number
  rbd_qty?: number
  rbd_cif?: number
  pko_qty?: number
  pko_cif?: number
  olive_qty?: number
  olive_cif?: number
  ten_percent_balance?: number
  juice_qty?: number
  juice_cif?: number
  ff_qty?: number
  df_qty?: number
  fruit_cocoa_qty?: number
  fruit_cocoa_cif?: number
  leavening_agent_qty?: number
  starch_1108_qty?: number
  starch_1108_cif?: number
  starch_3505_qty?: number
  milk_total_qty?: number
  cheese_qty?: number
  cheese_cif?: number
  swp_qty?: number
  swp_cif?: number
  wpc_qty?: number
  wpc_cif?: number
  pp_qty?: number
  aluminium_foil_qty?: number
  wastage_cif?: number
}

interface NotifGroup {
  notification_number: string
  license_count: number
  licenses: LicenseRow[]
  totals: NotifTotals
}

interface SionGroup {
  license_count: number
  totals: NotifTotals
  notifications: NotifGroup[]
}

interface ReportData {
  groups: SionGroup[]
}

interface Filters {
  is_expired: 'False' | 'True'
  is_null: 'False' | 'True'
  sion_norm: SionNorm
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface SionNormReportProps {
  sionNorm: SionNorm
  title: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatNum(num: number | null | undefined, decimals = 2): string {
  if (num === null || num === undefined) return '—'
  return Number(num).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  return formatDate(dateStr) || '—'
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TableHeaders() {
  return (
    <thead className="sticky top-0 z-10 bg-primary/10 text-[10px] text-foreground [&_th]:border [&_th]:border-border [&_th]:px-1.5 [&_th]:py-1 [&_th]:font-semibold">
      <tr>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '40px' }}>Sr</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '120px' }}>DFIA No</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '90px' }}>DFIA Dt</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '90px' }}>Expiry Dt</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '200px' }}>Exporter</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '100px' }}>Total CIF</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '100px' }}>Balance CIF</th>
        <th colSpan={9} className="text-center">Vegetable Oil</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '80px' }}>10% Bal</th>
        <th colSpan={4} className="text-center">Juice</th>
        <th colSpan={4} className="text-center">Food Flavour</th>
        <th colSpan={2} className="text-center">Fruit</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '60px' }}>Lvng Agt</th>
        <th colSpan={2} className="text-center">Starch 1108</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '60px' }}>Strch 3505</th>
        <th colSpan={8} className="text-center">Milk &amp; Milk</th>
        <th colSpan={3} className="text-center">PP</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '60px' }}>Al Foil</th>
        <th rowSpan={2} style={{ verticalAlign: 'middle', minWidth: '80px' }}>Wastage</th>
      </tr>
      <tr>
        <th style={{ minWidth: '80px' }}>HSN</th>
        <th style={{ minWidth: '120px' }}>PD</th>
        <th style={{ minWidth: '70px' }}>Tot Qty</th>
        <th style={{ minWidth: '70px' }}>RBD Qty</th>
        <th style={{ minWidth: '80px' }}>RBD CIF</th>
        <th style={{ minWidth: '70px' }}>PKO Qty</th>
        <th style={{ minWidth: '80px' }}>PKO CIF</th>
        <th style={{ minWidth: '70px' }}>Olv Qty</th>
        <th style={{ minWidth: '80px' }}>Olv CIF</th>
        <th style={{ minWidth: '80px' }}>HSN</th>
        <th style={{ minWidth: '100px' }}>PD</th>
        <th style={{ minWidth: '70px' }}>Qty</th>
        <th style={{ minWidth: '80px' }}>CIF</th>
        <th style={{ minWidth: '80px' }}>HSN</th>
        <th style={{ minWidth: '100px' }}>PD</th>
        <th style={{ minWidth: '60px' }}>FF Qty</th>
        <th style={{ minWidth: '60px' }}>DF Qty</th>
        <th style={{ minWidth: '60px' }}>Qty</th>
        <th style={{ minWidth: '80px' }}>CIF</th>
        <th style={{ minWidth: '60px' }}>Qty</th>
        <th style={{ minWidth: '80px' }}>CIF</th>
        <th style={{ minWidth: '120px' }}>PD</th>
        <th style={{ minWidth: '70px' }}>Tot Qty</th>
        <th style={{ minWidth: '60px' }}>Chz Qty</th>
        <th style={{ minWidth: '80px' }}>Chz CIF</th>
        <th style={{ minWidth: '60px' }}>SWP Qty</th>
        <th style={{ minWidth: '80px' }}>SWP CIF</th>
        <th style={{ minWidth: '60px' }}>WPC Qty</th>
        <th style={{ minWidth: '80px' }}>WPC CIF</th>
        <th style={{ minWidth: '80px' }}>HSN</th>
        <th style={{ minWidth: '100px' }}>PD</th>
        <th style={{ minWidth: '60px' }}>Qty</th>
      </tr>
    </thead>
  )
}

function LicenseRow({ license, index }: { license: LicenseRow; index: number }) {
  return (
    <tr
      className="border-b border-border/60 [&_td]:border [&_td]:border-border/50 [&_td]:px-1.5 [&_td]:py-1"
      style={{ fontSize: '9px' }}
    >
      <td>{index + 1}</td>
      <td>
        <Link
          to={`/licenses/${license.id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary no-underline"
          style={{ fontSize: '9px' }}
        >
          {license.license_number}
        </Link>
      </td>
      <td>{fmtDate(license.license_date)}</td>
      <td>{fmtDate(license.license_expiry_date)}</td>
      <td style={{ fontSize: '8px' }}>{license.exporter_name}</td>
      <td className="text-end">{formatNum(license.total_cif)}</td>
      <td className="text-end">{formatNum(license.balance_cif)}</td>
      <td>{license.vegetable_oil?.hsn_code}</td>
      <td style={{ fontSize: '7px' }}>{license.vegetable_oil?.description}</td>
      <td className="text-end">{formatNum(license.vegetable_oil?.total_qty)}</td>
      <td className="text-end">{formatNum(license.vegetable_oil?.rbd_qty)}</td>
      <td className="text-end">{formatNum(license.vegetable_oil?.rbd_cif)}</td>
      <td className="text-end">{formatNum(license.vegetable_oil?.pko_qty)}</td>
      <td className="text-end">{formatNum(license.vegetable_oil?.pko_cif)}</td>
      <td className="text-end">{formatNum(license.vegetable_oil?.olive_qty)}</td>
      <td className="text-end">{formatNum(license.vegetable_oil?.olive_cif)}</td>
      <td className="text-end">{formatNum(license.ten_percent_balance)}</td>
      <td>{license.juice?.hsn_code}</td>
      <td style={{ fontSize: '7px' }}>{license.juice?.description}</td>
      <td className="text-end">{formatNum(license.juice?.qty)}</td>
      <td className="text-end">{formatNum(license.juice?.cif)}</td>
      <td>{license.food_flavour?.hsn_code}</td>
      <td style={{ fontSize: '7px' }}>{license.food_flavour?.description}</td>
      <td className="text-end">{formatNum(license.food_flavour?.ff_qty)}</td>
      <td className="text-end">{formatNum(license.food_flavour?.df_qty)}</td>
      <td className="text-end">{formatNum(license.fruit_cocoa?.qty)}</td>
      <td className="text-end">{formatNum(license.fruit_cocoa?.cif)}</td>
      <td className="text-end">{formatNum(license.leavening_agent?.qty)}</td>
      <td className="text-end">{formatNum(license.starch_1108?.qty)}</td>
      <td className="text-end">{formatNum(license.starch_1108?.cif)}</td>
      <td className="text-end">{formatNum(license.starch_3505?.qty)}</td>
      <td style={{ fontSize: '7px' }}>{license.milk_and_milk?.description}</td>
      <td className="text-end">{formatNum(license.milk_and_milk?.total_qty)}</td>
      <td className="text-end">{formatNum(license.milk_and_milk?.cheese_qty)}</td>
      <td className="text-end">{formatNum(license.milk_and_milk?.cheese_cif)}</td>
      <td className="text-end">{formatNum(license.milk_and_milk?.swp_qty)}</td>
      <td className="text-end">{formatNum(license.milk_and_milk?.swp_cif)}</td>
      <td className="text-end">{formatNum(license.milk_and_milk?.wpc_qty)}</td>
      <td className="text-end">{formatNum(license.milk_and_milk?.wpc_cif)}</td>
      <td>{license.pp?.hsn_code}</td>
      <td style={{ fontSize: '7px' }}>{license.pp?.description}</td>
      <td className="text-end">{formatNum(license.pp?.qty)}</td>
      <td className="text-end">{formatNum(license.aluminium_foil?.qty)}</td>
      <td className="text-end">{formatNum(license.wastage_cif)}</td>
    </tr>
  )
}

function TotalsRow({ totals, label }: { totals: NotifTotals; label: string }) {
  return (
    <tr
      className="bg-warning/15 font-bold text-warning [&_td]:border [&_td]:border-border/50 [&_td]:px-1.5 [&_td]:py-1"
      style={{ fontSize: '9px' }}
    >
      <td colSpan={5} className="text-end">{label}:</td>
      <td className="text-end">{formatNum(totals.total_cif)}</td>
      <td className="text-end">{formatNum(totals.balance_cif)}</td>
      <td colSpan={2}></td>
      <td className="text-end">{formatNum(totals.veg_oil_total_qty)}</td>
      <td className="text-end">{formatNum(totals.rbd_qty)}</td>
      <td className="text-end">{formatNum(totals.rbd_cif)}</td>
      <td className="text-end">{formatNum(totals.pko_qty)}</td>
      <td className="text-end">{formatNum(totals.pko_cif)}</td>
      <td className="text-end">{formatNum(totals.olive_qty)}</td>
      <td className="text-end">{formatNum(totals.olive_cif)}</td>
      <td className="text-end">{formatNum(totals.ten_percent_balance)}</td>
      <td colSpan={2}></td>
      <td className="text-end">{formatNum(totals.juice_qty)}</td>
      <td className="text-end">{formatNum(totals.juice_cif)}</td>
      <td colSpan={2}></td>
      <td className="text-end">{formatNum(totals.ff_qty)}</td>
      <td className="text-end">{formatNum(totals.df_qty)}</td>
      <td className="text-end">{formatNum(totals.fruit_cocoa_qty)}</td>
      <td className="text-end">{formatNum(totals.fruit_cocoa_cif)}</td>
      <td className="text-end">{formatNum(totals.leavening_agent_qty)}</td>
      <td className="text-end">{formatNum(totals.starch_1108_qty)}</td>
      <td className="text-end">{formatNum(totals.starch_1108_cif)}</td>
      <td className="text-end">{formatNum(totals.starch_3505_qty)}</td>
      <td></td>
      <td className="text-end">{formatNum(totals.milk_total_qty)}</td>
      <td className="text-end">{formatNum(totals.cheese_qty)}</td>
      <td className="text-end">{formatNum(totals.cheese_cif)}</td>
      <td className="text-end">{formatNum(totals.swp_qty)}</td>
      <td className="text-end">{formatNum(totals.swp_cif)}</td>
      <td className="text-end">{formatNum(totals.wpc_qty)}</td>
      <td className="text-end">{formatNum(totals.wpc_cif)}</td>
      <td colSpan={2}></td>
      <td className="text-end">{formatNum(totals.pp_qty)}</td>
      <td className="text-end">{formatNum(totals.aluminium_foil_qty)}</td>
      <td className="text-end">{formatNum(totals.wastage_cif)}</td>
    </tr>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function SionNormReport({ sionNorm, title }: SionNormReportProps) {
  const [data, setData] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<Filters>({
    is_expired: 'False',
    is_null: 'False',
    sion_norm: sionNorm,
  })

  useEffect(() => {
    const controller = new AbortController()
    const fetchReport = async () => {
      try {
        setLoading(true)
        const response = await apiClient.get<ReportData>(ENDPOINTS.LICENSES.ACTIVE_DFIA_REPORT, {
          params: filters,
          signal: controller.signal,
        })
        setData(response.data)
      } catch (error: unknown) {
        if ((error as { name?: string }).name === 'CanceledError') return
        toast.error('Failed to load report data. Please try again.')
      } finally {
        setLoading(false)
      }
    }
    void fetchReport()
    return () => controller.abort()
  }, [filters])

  const handleFilterChange = (filterName: keyof Filters, value: string) =>
    setFilters((prev) => ({ ...prev, [filterName]: value }))

  const EXPIRED_OPTIONS: [string, string][] = [
    ['False', 'Active'],
    ['True', 'Expired'],
  ]
  const NULL_OPTIONS: [string, string][] = [
    ['False', '> 200'],
    ['True', '< 200'],
  ]

  function FilterRadios() {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1.5 text-xs font-medium text-muted-foreground">Active / Expired</div>
          <div className="flex gap-4">
            {EXPIRED_OPTIONS.map(([val, lbl]) => (
              <label key={val} className="flex cursor-pointer items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  className="accent-primary"
                  checked={filters.is_expired === val}
                  onChange={() => handleFilterChange('is_expired', val as 'False' | 'True')}
                />
                {lbl}
              </label>
            ))}
          </div>
        </div>
        <div>
          <div className="mb-1.5 text-xs font-medium text-muted-foreground">Balance CIF</div>
          <div className="flex gap-4">
            {NULL_OPTIONS.map(([val, lbl]) => (
              <label key={val} className="flex cursor-pointer items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  className="accent-primary"
                  checked={filters.is_null === val}
                  onChange={() => handleFilterChange('is_null', val as 'False' | 'True')}
                />
                {lbl}
              </label>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <>
        <div className="mb-6">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reports</p>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        </div>
        <div className="flex items-center gap-2 p-6 text-muted-foreground">
          <Loader2 className="size-5 animate-spin text-primary" /> Loading…
        </div>
      </>
    )
  }

  const pageHeader = (
    <div className="mb-6">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reports</p>
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
    </div>
  )

  if (!data || !data.groups || data.groups.length === 0) {
    return (
      <>
        {pageHeader}
        <Card className="mb-4">
          <CardContent className="pt-5">
            <FilterRadios />
          </CardContent>
        </Card>
        <p className="text-sm text-muted-foreground">No records found for SION Norm {sionNorm}</p>
      </>
    )
  }

  const sionGroup = data.groups[0]
  let globalSrNo = 0

  return (
    <>
      {pageHeader}

      {/* Filters */}
      <Card className="mb-4">
        <CardContent className="pt-5">
          <FilterRadios />
        </CardContent>
      </Card>

      {/* Summary cards */}
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {([
          ['Total Licenses', String(sionGroup.license_count)],
          ['Total CIF', formatNum(sionGroup.totals.total_cif)],
          ['Balance CIF', formatNum(sionGroup.totals.balance_cif)],
        ] as [string, string][]).map(([label, value]) => (
          <Card key={label}>
            <CardContent className="pt-5">
              <div className="text-xs font-medium text-muted-foreground">{label}</div>
              <div className="mt-1 text-2xl font-semibold tracking-tight text-foreground tabular-nums">
                {value}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tables by notification */}
      {sionGroup.notifications.map((notifGroup, notifIndex) => (
        <div key={notifIndex} className="mb-4">
          <div className="mb-3 flex items-center gap-3 rounded-md bg-muted px-3 py-2">
            <span className="text-sm font-semibold text-foreground">
              Notification: {notifGroup.notification_number}
            </span>
            <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {notifGroup.license_count} licenses
            </span>
          </div>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-auto" style={{ maxHeight: '600px' }}>
                <table className="w-full border-collapse">
                  <TableHeaders />
                  <tbody>
                    {notifGroup.licenses.map((license) => {
                      globalSrNo++
                      return <LicenseRow key={license.id} license={license} index={globalSrNo - 1} />
                    })}
                    <TotalsRow
                      totals={notifGroup.totals}
                      label={`Total - ${notifGroup.notification_number}`}
                    />
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      ))}

      {/* Grand total */}
      <Card className="mt-4 border-success/40">
        <div className="rounded-t-xl border-b border-success/30 bg-success/10 px-4 py-2.5 text-sm font-semibold text-success">
          Grand Total — SION Norm {sionNorm}
        </div>
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full border-collapse">
              <TableHeaders />
              <tbody>
                <TotalsRow totals={sionGroup.totals} label="Grand Total" />
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
