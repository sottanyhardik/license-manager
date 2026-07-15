// TransferLetterForm — port from legacy/frontend/src/components/TransferLetterForm.tsx
// Multi-recipient form for generating transfer letters (ZIP or PDF).
// Adapted to new stack: no react-select; uses native inputs + async fetch for companies/templates.

import { useEffect, useMemo, useState } from 'react'
import {
  CheckCircle,
  ClipboardList,
  FileArchive,
  FileText,
  Info,
  Loader2,
  Plus,
  Send,
  Trash2,
  Users,
  X,
} from 'lucide-react'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { cn } from '@/shared/utils/cn'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface TransferLetterItem {
  id: number
  license_number: string
  cif_fc: number | string
  purchase_status?: string
}

interface Party {
  id: number
  company_name: string
  addressLine1: string
  addressLine2: string
  template_id: string
  template_label: string
}

interface GroupedItem {
  license_number: string
  purchase_status: string
  item_ids: number[]
  total_cif: number
}

interface TemplateOption {
  id: number
  name: string
}

interface CompanyOption {
  id: number
  name: string
  address_line_1?: string
  address_line_2?: string
}

interface TransferLetterFormProps {
  instanceId: string | number
  instanceType?: 'allotment' | 'trade' | 'boe'
  instanceIdentifier?: string
  items?: TransferLetterItem[]
  disabled?: boolean
  onSuccess?: (msg: string) => void
  onError?: (msg: string) => void
}

// ─── Purchase status colour map ────────────────────────────────────────────────

const PS_COLORS: Record<string, { bg: string; color: string }> = {
  GE: { bg: '#DBEAFE', color: '#1E3A8A' },
  MI: { bg: '#D1FAE5', color: 'var(--tb-success-text, #065f46)' },
  CO: { bg: '#EDE9FE', color: '#5B21B6' },
  PP: { bg: '#FED7AA', color: '#7C2D12' },
  SM: { bg: '#FCE7F3', color: '#831843' },
  GO: { bg: '#E2E8F0', color: '#1E293B' },
}
const getPsStyle = (s: string) =>
  PS_COLORS[s] ?? { bg: 'var(--tb-sunken)', color: 'var(--tb-text-secondary)' }

// ─── API helpers ───────────────────────────────────────────────────────────────

async function searchCompanies(q: string): Promise<CompanyOption[]> {
  try {
    const { data } = await apiClient.get<{ data?: CompanyOption[] } | CompanyOption[]>(
      `${ENDPOINTS.MASTERS.COMPANIES}?search=${encodeURIComponent(q)}`,
    )
    const list = Array.isArray(data)
      ? data
      : (data as { data?: CompanyOption[] }).data ?? []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

async function fetchCompany(id: number): Promise<CompanyOption | null> {
  try {
    const { data } = await apiClient.get<CompanyOption>(ENDPOINTS.MASTERS.COMPANY(id))
    return data
  } catch {
    return null
  }
}

async function searchTemplates(q: string): Promise<TemplateOption[]> {
  try {
    const { data } = await apiClient.get<
      { data?: TemplateOption[] } | TemplateOption[]
    >(
      `${ENDPOINTS.TRANSFER_LETTERS.LIST}?search=${encodeURIComponent(q)}`,
    )
    const list = Array.isArray(data)
      ? data
      : (data as { data?: TemplateOption[] }).data ?? []
    return Array.isArray(list) ? list : []
  } catch {
    return []
  }
}

// ─── Component ─────────────────────────────────────────────────────────────────

export default function TransferLetterForm({
  instanceId,
  instanceType = 'allotment',
  instanceIdentifier,
  items = [],
  disabled = false,
  onSuccess,
  onError,
}: TransferLetterFormProps) {
  const [parties, setParties] = useState<Party[]>([
    {
      id: 1,
      company_name: '',
      addressLine1: '',
      addressLine2: '',
      template_id: '',
      template_label: '',
    },
  ])

  // Company autocomplete state per party
  const [companySearches, setCompanySearches] = useState<Record<number, string>>({})
  const [companySuggestions, setCompanySuggestions] = useState<
    Record<number, CompanyOption[]>
  >({})

  // Template autocomplete state per party
  const [templateSearches, setTemplateSearches] = useState<Record<number, string>>({})
  const [templateSuggestions, setTemplateSuggestions] = useState<
    Record<number, TemplateOption[]>
  >({})

  const [licenseEdits, setLicenseEdits] = useState<Record<string, string>>({})
  const [generating, setGenerating] = useState<
    null | 'without_copy' | 'with_copy' | 'pdf'
  >(null)
  const [selectedItems, setSelectedItems] = useState<number[]>(
    items.map((item) => item.id),
  )

  useEffect(() => {
    setSelectedItems(items.map((item) => item.id))
  }, [items])

  const groupedItems = useMemo<GroupedItem[]>(() => {
    const groups: Record<string, GroupedItem> = {}
    items.forEach((item) => {
      const key = String(item.license_number ?? '-')
      if (!groups[key]) {
        groups[key] = {
          license_number: key,
          purchase_status: item.purchase_status ?? 'N/A',
          item_ids: [],
          total_cif: 0,
        }
      }
      groups[key].item_ids.push(item.id)
      groups[key].total_cif += parseFloat(String(item.cif_fc ?? 0))
    })
    return Object.values(groups)
  }, [items])

  // ─── Party management ────────────────────────────────────────────────────────

  const addParty = () =>
    setParties((prev) => [
      ...prev,
      {
        id: Date.now(),
        company_name: '',
        addressLine1: '',
        addressLine2: '',
        template_id: '',
        template_label: '',
      },
    ])

  const removeParty = (id: number) =>
    setParties((prev) => prev.filter((p) => p.id !== id))

  const updateParty = (id: number, updates: Partial<Party>) =>
    setParties((prev) =>
      prev.map((p) => (p.id === id ? { ...p, ...updates } : p)),
    )

  // Company search handlers
  const handleCompanySearch = async (partyId: number, q: string) => {
    setCompanySearches((prev) => ({ ...prev, [partyId]: q }))
    if (q.length < 2) {
      setCompanySuggestions((prev) => ({ ...prev, [partyId]: [] }))
      return
    }
    const results = await searchCompanies(q)
    setCompanySuggestions((prev) => ({ ...prev, [partyId]: results }))
  }

  const handleSelectCompany = async (partyId: number, company: CompanyOption) => {
    setCompanySearches((prev) => ({ ...prev, [partyId]: company.name }))
    setCompanySuggestions((prev) => ({ ...prev, [partyId]: [] }))
    updateParty(partyId, { company_name: company.name })
    // Auto-fill address
    const detail = await fetchCompany(company.id)
    if (detail) {
      updateParty(partyId, {
        company_name: company.name,
        addressLine1: detail.address_line_1 ?? '',
        addressLine2: detail.address_line_2 ?? '',
      })
    }
  }

  // Template search handlers
  const handleTemplateSearch = async (partyId: number, q: string) => {
    setTemplateSearches((prev) => ({ ...prev, [partyId]: q }))
    const results = await searchTemplates(q)
    setTemplateSuggestions((prev) => ({ ...prev, [partyId]: results }))
  }

  const handleSelectTemplate = (partyId: number, template: TemplateOption) => {
    setTemplateSearches((prev) => ({ ...prev, [partyId]: template.name }))
    setTemplateSuggestions((prev) => ({ ...prev, [partyId]: [] }))
    updateParty(partyId, {
      template_id: String(template.id),
      template_label: template.name,
    })
  }

  // ─── Item selection ──────────────────────────────────────────────────────────

  const isGroupSelected = (licenseNumber: string) => {
    const group = groupedItems.find((g) => g.license_number === licenseNumber)
    return group?.item_ids.every((id) => selectedItems.includes(id)) ?? false
  }

  const toggleGroup = (licenseNumber: string) => {
    const group = groupedItems.find((g) => g.license_number === licenseNumber)
    if (!group) return
    if (isGroupSelected(licenseNumber)) {
      setSelectedItems((prev) =>
        prev.filter((id) => !group.item_ids.includes(id)),
      )
    } else {
      setSelectedItems((prev) => [...new Set([...prev, ...group.item_ids])])
    }
  }

  // ─── Generate ────────────────────────────────────────────────────────────────

  const validParties = parties.filter(
    (p) => p.company_name.trim() && p.template_id,
  )

  const selectedCount = groupedItems.filter((g) =>
    isGroupSelected(g.license_number),
  ).length

  const genDisabled =
    generating !== null ||
    disabled ||
    validParties.length === 0 ||
    selectedItems.length === 0 ||
    selectedCount === 0

  const handleGenerate = async (
    includeLicenseCopy = true,
    format: 'zip' | 'pdf' = 'zip',
  ) => {
    const partiesWithoutTemplate = parties.filter(
      (p) => p.company_name.trim() && !p.template_id,
    )
    if (partiesWithoutTemplate.length > 0) {
      onError?.('Please select a template for all parties')
      return
    }
    if (validParties.length === 0) {
      onError?.(
        'Please enter at least one company name and select its template',
      )
      return
    }
    const selectedGroups = groupedItems.filter((g) =>
      isGroupSelected(g.license_number),
    )
    if (selectedGroups.length === 0) {
      onError?.('Please select at least one license to generate transfer letter')
      return
    }

    setGenerating(
      format === 'pdf' ? 'pdf' : includeLicenseCopy ? 'with_copy' : 'without_copy',
    )

    const filteredCifEdits: Record<string, string | number> = {}
    groupedItems.forEach((group) => {
      const editedTotal = licenseEdits[group.license_number]
      if (editedTotal !== undefined) {
        const activeIds = group.item_ids.filter((id) =>
          selectedItems.includes(id),
        )
        activeIds.forEach((id, idx) => {
          filteredCifEdits[id] = idx === 0 ? editedTotal : '0'
        })
      }
    })

    const requestData = {
      parties: validParties.map((p) => ({
        company_name: p.company_name.trim(),
        address_line1: p.addressLine1.trim(),
        address_line2: p.addressLine2.trim(),
        template_id: p.template_id,
      })),
      cif_edits: filteredCifEdits,
      include_license_copy: format === 'pdf' ? true : includeLicenseCopy,
      selected_items: selectedItems,
      include_todays_date: true,
      format,
    }

    try {
      const endpoint =
        instanceType === 'allotment'
          ? ENDPOINTS.ALLOTMENTS.GENERATE_TRANSFER_LETTER(Number(instanceId))
          : instanceType === 'trade'
          ? `/api/v1/trades/${instanceId}/generate-transfer-letter/`
          : `/api/v1/bill-of-entries/${instanceId}/generate-transfer-letter/`

      const response = await apiClient.post(endpoint, requestData, {
        responseType: 'blob',
      })

      const identifier = instanceIdentifier ?? instanceId
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute(
        'download',
        format === 'pdf'
          ? `TransferLetter_${instanceType}_${identifier}.pdf`
          : `TransferLetter_${instanceType}_${identifier}_${
              includeLicenseCopy ? 'WithCopy' : 'WithoutCopy'
            }.zip`,
      )
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)

      onSuccess?.(
        format === 'pdf'
          ? 'Transfer letter PDF generated'
          : validParties.length > 1
          ? `Transfer letters for ${validParties.length} parties generated`
          : `Transfer letter ${includeLicenseCopy ? 'with' : 'without'} license copy generated`,
      )
    } catch (err: unknown) {
      const e = err as { response?: { data?: { error?: string } } }
      onError?.(e.response?.data?.error ?? 'Failed to generate transfer letter')
    } finally {
      setGenerating(null)
    }
  }

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {/* Header */}
      <div
        className="flex items-center gap-3 border-b border-border/60 px-5 py-3.5"
        style={{
          background:
            'linear-gradient(135deg, var(--tb-brand-50), var(--tb-card-bg))',
        }}
      >
        <div
          className="flex size-9 shrink-0 items-center justify-center rounded-lg"
          style={{
            background: 'var(--tb-brand)',
            boxShadow: '0 2px 8px rgba(59,130,246,.25)',
          }}
        >
          <Send className="size-4 text-white" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-[13px] font-bold leading-tight tracking-tight text-foreground">
            Generate Transfer Letter
          </h2>
          <p className="text-[11px] text-muted-foreground">
            {validParties.length > 0
              ? `${validParties.length} recipient${validParties.length > 1 ? 's' : ''} ready`
              : 'Add recipients to generate'}
            {selectedCount > 0 &&
              ` · ${selectedCount} license${selectedCount > 1 ? 's' : ''} selected`}
          </p>
        </div>
        {validParties.length > 0 && selectedCount > 0 && (
          <div
            className="ml-auto flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
            style={{
              background: 'var(--tb-success-soft)',
              color: 'var(--tb-success-text)',
            }}
          >
            <CheckCircle className="size-3.5" />
            {validParties.length} party · {selectedCount} license
          </div>
        )}
      </div>

      <div className="px-5 py-4">
        {/* Recipients */}
        <div className="mb-5">
          <div className="mb-2.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users className="size-3.5 text-muted-foreground" />
              <span className="text-[12px] font-bold uppercase tracking-wider text-muted-foreground">
                Recipients
              </span>
              {parties.length > 1 && (
                <span
                  className="flex items-center justify-center rounded-full text-[10px] font-bold text-white"
                  style={{
                    background: 'var(--tb-brand)',
                    width: 18,
                    height: 18,
                    lineHeight: 1,
                  }}
                >
                  {parties.length}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={addParty}
              disabled={disabled}
              className="flex items-center gap-1 rounded-md border border-dashed border-border px-2.5 py-1 text-[11.5px] font-semibold text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            >
              <Plus className="size-3.5" />
              Add Party
            </button>
          </div>

          <div className="flex flex-col gap-2">
            {parties.map((party, idx) => (
              <div
                key={party.id}
                className="group flex flex-wrap items-start gap-2 rounded-lg border border-border/70 bg-background px-3 py-2.5 transition-shadow hover:shadow-sm"
              >
                {parties.length > 1 && (
                  <span
                    className="flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                    style={{ background: 'var(--tb-brand)', minWidth: 20 }}
                  >
                    {idx + 1}
                  </span>
                )}

                {/* Company autocomplete */}
                <div className="relative min-w-[200px] flex-[2]">
                  <Input
                    className="h-[34px] text-sm"
                    value={companySearches[party.id] ?? party.company_name}
                    onChange={(e) =>
                      handleCompanySearch(party.id, e.target.value)
                    }
                    onBlur={() => {
                      // Commit whatever is typed as the company name
                      const typed = companySearches[party.id] ?? party.company_name
                      updateParty(party.id, { company_name: typed })
                    }}
                    placeholder="Company name..."
                    disabled={disabled}
                  />
                  {(companySuggestions[party.id]?.length ?? 0) > 0 && (
                    <ul className="absolute z-20 mt-1 w-full rounded-md border border-border bg-background shadow-lg">
                      {companySuggestions[party.id].map((c) => (
                        <li
                          key={c.id}
                          className="cursor-pointer px-3 py-1.5 text-sm hover:bg-muted"
                          onMouseDown={() => handleSelectCompany(party.id, c)}
                        >
                          {c.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <Input
                  className="h-[34px] min-w-[140px] flex-[1.5] text-sm"
                  value={party.addressLine1}
                  onChange={(e) =>
                    updateParty(party.id, { addressLine1: e.target.value })
                  }
                  placeholder="Address line 1"
                  disabled={disabled}
                />
                <Input
                  className="h-[34px] min-w-[140px] flex-[1.5] text-sm"
                  value={party.addressLine2}
                  onChange={(e) =>
                    updateParty(party.id, { addressLine2: e.target.value })
                  }
                  placeholder="Address line 2"
                  disabled={disabled}
                />

                {/* Template autocomplete */}
                <div className="relative min-w-[160px] flex-[1.5]">
                  <Input
                    className={cn(
                      'h-[34px] text-sm',
                      !party.template_id && party.company_name.trim()
                        ? 'border-yellow-400'
                        : '',
                    )}
                    value={templateSearches[party.id] ?? party.template_label}
                    onChange={(e) =>
                      handleTemplateSearch(party.id, e.target.value)
                    }
                    placeholder="Template..."
                    disabled={disabled}
                  />
                  {(templateSuggestions[party.id]?.length ?? 0) > 0 && (
                    <ul className="absolute z-20 mt-1 w-full rounded-md border border-border bg-background shadow-lg">
                      {templateSuggestions[party.id].map((t) => (
                        <li
                          key={t.id}
                          className="cursor-pointer px-3 py-1.5 text-sm hover:bg-muted"
                          onMouseDown={() => handleSelectTemplate(party.id, t)}
                        >
                          {t.name}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {parties.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeParty(party.id)}
                    disabled={disabled}
                    className="flex size-[34px] shrink-0 items-center justify-center rounded-md border border-border/70 text-muted-foreground transition-colors hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive"
                  >
                    <X className="size-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap justify-between gap-1.5 text-[11px] text-muted-foreground">
            <span>
              Type a company name to search, or enter a custom name directly
            </span>
            <span className="flex items-center gap-1 opacity-80">
              <Info className="size-3" />
              Today's date will be included automatically
            </span>
          </div>
        </div>

        {/* Items for Transfer Letter */}
        {groupedItems.length > 0 && (
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-2">
              <ClipboardList className="size-3.5 text-muted-foreground" />
              <span className="text-[12px] font-bold uppercase tracking-wider text-muted-foreground">
                Items for Transfer Letter
              </span>
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                style={{
                  background:
                    selectedCount > 0
                      ? 'var(--tb-brand-50)'
                      : 'var(--tb-sunken)',
                  color:
                    selectedCount > 0
                      ? 'var(--tb-brand)'
                      : 'var(--tb-text-secondary)',
                }}
              >
                {selectedCount} of {groupedItems.length} selected
              </span>
              {items.length > groupedItems.length && (
                <span className="text-[11px] text-muted-foreground">
                  ({items.length} rows merged by license)
                </span>
              )}
            </div>
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-left text-[10.5px] font-bold uppercase tracking-wider text-muted-foreground">
                    <th className="w-10 px-3 py-2.5">#</th>
                    <th className="px-3 py-2.5">License Number</th>
                    <th className="w-28 px-3 py-2.5">Purchase Status</th>
                    <th className="w-44 px-3 py-2.5">
                      Total CIF FC{' '}
                      <span className="font-normal normal-case opacity-60">
                        (editable)
                      </span>
                    </th>
                    <th className="w-16 px-3 py-2.5 text-center">Select</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {groupedItems.map((group, idx) => {
                    const isSelected = isGroupSelected(group.license_number)
                    const displayCif =
                      licenseEdits[group.license_number] !== undefined
                        ? licenseEdits[group.license_number]
                        : group.total_cif.toFixed(2)
                    const psStyle = getPsStyle(group.purchase_status)
                    return (
                      <tr
                        key={group.license_number}
                        className={cn(
                          'transition-colors',
                          isSelected
                            ? 'bg-background hover:bg-muted/30'
                            : 'bg-muted/20 opacity-50',
                        )}
                      >
                        <td className="px-3 py-2 text-muted-foreground">
                          {idx + 1}
                        </td>
                        <td className="px-3 py-2">
                          <span className="font-mono text-[13px] font-semibold text-foreground">
                            {group.license_number}
                          </span>
                          {group.item_ids.length > 1 && (
                            <span
                              className="ml-2 rounded px-1.5 py-0.5 text-[10px] font-semibold"
                              style={{
                                background: 'var(--tb-brand-50)',
                                color: 'var(--tb-brand)',
                              }}
                            >
                              {group.item_ids.length} rows
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className="rounded px-2 py-0.5 text-[11px] font-semibold"
                            style={{
                              background: psStyle.bg,
                              color: psStyle.color,
                            }}
                          >
                            {group.purchase_status || 'N/A'}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <Input
                            type="number"
                            className="h-8 font-mono text-sm"
                            value={displayCif}
                            onChange={(e) =>
                              setLicenseEdits((prev) => ({
                                ...prev,
                                [group.license_number]: e.target.value,
                              }))
                            }
                            step="0.01"
                            disabled={disabled || !isSelected}
                          />
                        </td>
                        <td className="px-3 py-2 text-center">
                          <button
                            type="button"
                            onClick={() => toggleGroup(group.license_number)}
                            disabled={disabled}
                            className={cn(
                              'flex size-7 items-center justify-center rounded-md border transition-colors',
                              isSelected
                                ? 'border-destructive/50 text-destructive hover:bg-destructive/10'
                                : 'border-primary/50 text-primary hover:bg-primary/10',
                            )}
                            title={
                              isSelected
                                ? 'Remove from transfer letter'
                                : 'Add to transfer letter'
                            }
                          >
                            {isSelected ? (
                              <Trash2 className="size-3" />
                            ) : (
                              <Plus className="size-3" />
                            )}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {groupedItems.length === 0 && (
          <div
            className="mb-5 flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3.5 py-2.5 text-[13px]"
            style={{ color: 'var(--tb-warning-text)' }}
          >
            <Info className="size-4 shrink-0" />
            No items found. Please add items first.
          </div>
        )}

        {/* Generate actions */}
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 bg-muted/30 px-4 py-3">
          <div className="text-[11.5px] text-muted-foreground">
            {genDisabled && validParties.length === 0 && (
              <span className="flex items-center gap-1">
                <Info className="size-3.5" />
                Add at least one recipient with a template to generate
              </span>
            )}
            {!genDisabled && (
              <span
                className="flex items-center gap-1 font-medium"
                style={{ color: 'var(--tb-success-text)' }}
              >
                <CheckCircle className="size-3.5" />
                Ready to generate for {validParties.length} recipient
                {validParties.length > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                generating === null && void handleGenerate(false, 'zip')
              }
              disabled={genDisabled}
            >
              {generating === 'without_copy' ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FileArchive className="size-3.5" />
              )}
              {generating === 'without_copy'
                ? 'Generating…'
                : `Without Copy (${selectedCount})`}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                generating === null && void handleGenerate(true, 'zip')
              }
              disabled={genDisabled}
            >
              {generating === 'with_copy' ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FileArchive className="size-3.5" />
              )}
              {generating === 'with_copy'
                ? 'Generating…'
                : `With Copy (${selectedCount}${
                    validParties.length > 1 ? ` × ${validParties.length}` : ''
                  })`}
            </Button>
            <Button
              size="sm"
              style={{
                background:
                  'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))',
                border: 'none',
                color: '#fff',
                boxShadow: '0 2px 8px rgba(59,130,246,.3)',
              }}
              onClick={() =>
                generating === null && void handleGenerate(true, 'pdf')
              }
              disabled={genDisabled}
            >
              {generating === 'pdf' ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FileText className="size-3.5" />
              )}
              {generating === 'pdf' ? 'Generating…' : 'Download PDF'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
