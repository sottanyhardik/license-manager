// LicenseDetail — detail page for a single license.
// Tabs: Overview | Import Items | History (Documents tab reserved)
// Overview: balance panel, inline-editable condition sheet & notes.
// Import Items: SR number table with expand-row BOE/allotment usage.
// "Edit" button (role-gated), "Download PDF / Excel" buttons.

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  Building2,
  Calendar,
  FileSpreadsheet,
  FileText,
  Loader2,
  Pencil,
  TriangleAlert,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/ui/button'
import { Skeleton } from '@/shared/ui/skeleton'
import { cn } from '@/shared/utils/cn'
import { formatDate } from '@/shared/utils/formatters'
import { useAuth } from '@/shared/auth/AuthContext'
import { ROLES } from '@/shared/auth/roles'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { useLicense } from '../queries'
import { LicenseStatusBadge } from '../components/LicenseStatusBadge'
import { LicenseBalancePanel } from '../components/LicenseBalancePanel'
import { LicenseImportItems } from '../components/LicenseImportItems'
import { LicenseExportItems } from '../components/LicenseExportItems'
import { LicenseDocuments } from '../components/LicenseDocuments'
import { LicenseHistory } from '../components/LicenseHistory'
import { LicenseFormModal } from '../components/LicenseFormModal'
import type { License } from '../types'

// ── Tab types ──────────────────────────────────────────────────────────────────

type Tab = 'overview' | 'import-items' | 'export-items' | 'documents' | 'history'

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'import-items', label: 'Import Items' },
  { id: 'export-items', label: 'Export Items' },
  { id: 'documents', label: 'Documents' },
  { id: 'history', label: 'History' },
]

// ── Header skeleton ───────────────────────────────────────────────────────────

function HeaderSkeleton() {
  return (
    <div className="space-y-3 p-6">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-5 w-96" />
      <div className="flex gap-4 pt-2">
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-10 w-24" />
      </div>
    </div>
  )
}

// ── License type pill ─────────────────────────────────────────────────────────

const TYPE_STYLES: Record<string, string> = {
  DFIA: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',
  RODTEP: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
  ROSTL: 'bg-teal-500/10 text-teal-700 dark:text-teal-400',
  MEIS: 'bg-orange-500/10 text-orange-700 dark:text-orange-400',
  INCENTIVE: 'bg-pink-500/10 text-pink-700 dark:text-pink-400',
}

function LicenseTypePill({ type }: { type: string }) {
  return (
    <span
      className={cn(
        'rounded-full px-2.5 py-0.5 text-xs font-semibold',
        TYPE_STYLES[type] ?? 'bg-muted text-muted-foreground',
      )}
    >
      {type}
    </span>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LicenseDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { hasRole, isSuperAdmin } = useAuth()
  const canEdit = hasRole(ROLES.LICENSE_MANAGER) || isSuperAdmin()

  const licenseId = id ? parseInt(id, 10) : null

  const { data: license, isLoading, isError } = useLicense(licenseId)

  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [editOpen, setEditOpen] = useState(false)
  const [localOverrides, setLocalOverrides] = useState<Partial<License>>({})
  const [pdfLoading, setPdfLoading] = useState(false)
  const [excelLoading, setExcelLoading] = useState(false)

  // Merge server data with optimistic local overrides (from inline edits).
  const merged: License | null = license
    ? ({ ...license, ...localOverrides } as License)
    : null

  // ── Download handlers ────────────────────────────────────────────────────────

  async function handleDownloadPDF() {
    if (!licenseId) return
    setPdfLoading(true)
    try {
      toast.info('Generating PDF…')
      const response = await apiClient.get(ENDPOINTS.LICENSES.BALANCE_PDF(licenseId), {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${merged?.license_number ?? licenseId}-balance.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.success('PDF downloaded.')
    } catch {
      toast.error('Failed to generate PDF.')
    } finally {
      setPdfLoading(false)
    }
  }

  async function handleDownloadExcel() {
    if (!licenseId) return
    setExcelLoading(true)
    try {
      toast.info('Generating Excel…')
      const response = await apiClient.get(ENDPOINTS.LICENSES.BALANCE_EXCEL, {
        params: { license_id: licenseId },
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${merged?.license_number ?? licenseId}-balance.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.success('Excel downloaded.')
    } catch {
      toast.error('Failed to generate Excel.')
    } finally {
      setExcelLoading(false)
    }
  }

  // ── Error / loading states ────────────────────────────────────────────────────

  if (!licenseId || isNaN(licenseId)) {
    return (
      <div className="p-6 text-center text-destructive">
        Invalid license ID.
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="border-b bg-card">
          <HeaderSkeleton />
        </div>
      </div>
    )
  }

  if (isError || !merged) {
    return (
      <div className="p-6">
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          Failed to load license.
        </div>
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          Go Back
        </Button>
      </div>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card px-6 py-5">
        <div className="mb-4 flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="gap-1"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            Back
          </Button>
        </div>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          {/* License identity */}
          <div>
            <div className="mb-1 flex items-center gap-2 flex-wrap">
              <FileText className="size-5 text-muted-foreground" aria-hidden="true" />
              <h1 className="font-mono text-xl font-bold">{merged.license_number}</h1>
              <LicenseTypePill type={merged.license_type ?? ''} />
              <LicenseStatusBadge
                isExpired={merged.is_expired ?? false}
                expiryDate={merged.license_expiry_date ?? ''}
                flags={merged.flags}
              />
            </div>
            <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              {merged.company_label && (
                <div className="flex items-center gap-1">
                  <Building2 className="size-3.5" aria-hidden="true" />
                  <span>{merged.company_label}</span>
                </div>
              )}
              <div className="flex items-center gap-1">
                <Calendar className="size-3.5" aria-hidden="true" />
                <span>Issued {formatDate(merged.license_date)}</span>
              </div>
              <div className="flex items-center gap-1">
                <Calendar className="size-3.5" aria-hidden="true" />
                <span>Expires {formatDate(merged.license_expiry_date)}</span>
              </div>
              {merged.exporter_name && (
                <div>Exporter: {merged.exporter_name}</div>
              )}
              {merged.port_name && <div>Port: {merged.port_name}</div>}
            </dl>
          </div>

          {/* Action buttons */}
          <div className="flex shrink-0 flex-wrap gap-2">
            {canEdit && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditOpen(true)}
              >
                <Pencil className="size-3.5" aria-hidden="true" />
                Edit
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadPDF}
              disabled={pdfLoading}
            >
              {pdfLoading ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <FileText className="size-3.5" aria-hidden="true" />
              )}
              Download PDF
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadExcel}
              disabled={excelLoading}
            >
              {excelLoading ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <FileSpreadsheet className="size-3.5" aria-hidden="true" />
              )}
              Download Excel
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="mt-4 flex gap-0 border-b" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                activeTab === tab.id
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="p-6">
        {activeTab === 'overview' && (
          <div role="tabpanel" aria-label="Overview">
            <LicenseBalancePanel
              license={merged}
              onUpdate={(updates) =>
                setLocalOverrides((prev) => ({ ...prev, ...updates }))
              }
            />
          </div>
        )}

        {activeTab === 'import-items' && (
          <div role="tabpanel" aria-label="Import Items">
            {merged.import_license && merged.import_license.length > 0 ? (
              <LicenseImportItems
                licenseId={merged.id}
                items={merged.import_license}
              />
            ) : (
              <div className="py-10 text-center text-sm text-muted-foreground">
                No import items for this license.
              </div>
            )}
          </div>
        )}

        {activeTab === 'export-items' && (
          <div role="tabpanel" aria-label="Export Items">
            <LicenseExportItems licenseId={merged.id} />
          </div>
        )}

        {activeTab === 'documents' && (
          <div role="tabpanel" aria-label="Documents">
            <LicenseDocuments licenseId={merged.id} />
          </div>
        )}

        {activeTab === 'history' && (
          <div role="tabpanel" aria-label="History">
            <LicenseHistory licenseId={merged.id} />
          </div>
        )}
      </div>

      {/* Edit modal */}
      {canEdit && (
        <LicenseFormModal
          open={editOpen}
          onOpenChange={setEditOpen}
          license={merged}
        />
      )}
    </div>
  )
}
