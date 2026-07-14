// MasterList — generic master list page driven by entity name in the URL.
//
// Route: /masters/:entity
// e.g.  /masters/companies, /masters/ports, /masters/hs-codes
//
// Each entity has a column definition registered in ENTITY_CONFIG below.
// Adding a new master entity requires only a new entry there — no new page file.
//
// Write access (create / edit / delete) is restricted to superusers only for
// master data, matching the legacy system's permission model.

import { useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Plus, TriangleAlert } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'
import { useAuth } from '@/shared/auth/AuthContext'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { MasterDataTable } from '../components/MasterDataTable'
import {
  useCompanies, useDeleteCompany,
  usePorts, useDeletePort,
  useHSCodes, useDeleteHSCode,
  useItemGroups, useDeleteItemGroup,
  useItemNames, useDeleteItemName,
  useSionNormClasses, useDeleteSionNormClass,
  useExchangeRates, useDeleteExchangeRate,
} from '../queries'
import type {
  Company, Port, HSCode, ItemGroup, ItemName, SionNormClass, ExchangeRate,
  PaginatedResponse,
} from '../types'
import type { UseQueryResult, UseMutationResult } from '@tanstack/react-query'

// ─── Entity configuration ─────────────────────────────────────────────────────

interface EntityConfig<T> {
  label: string
  columns: ColumnDef<T, unknown>[]
  useList: (params: { search?: string; page: number; page_size: number; ordering?: string }) => UseQueryResult<PaginatedResponse<T>>
  useDelete: () => UseMutationResult<void, Error, number>
  getId: (row: T) => number
  searchPlaceholder?: string
}

// We need to satisfy TypeScript with typed per-entity configs but expose them
// through a common Record. The cast at the call-site is safe because the entity
// name from useParams is validated against the keys before use.

type AnyEntityConfig = EntityConfig<Record<string, unknown>>

const ENTITY_CONFIG: Record<string, AnyEntityConfig> = {
  companies: {
    label: 'Companies',
    searchPlaceholder: 'Search by name, city, GSTIN...',
    columns: [
      { accessorKey: 'name', header: 'Name', enableSorting: true },
      { accessorKey: 'city', header: 'City', enableSorting: true,
        cell: ({ getValue }) => (getValue() as string | undefined) ?? '—' },
      { accessorKey: 'state', header: 'State', enableSorting: false,
        cell: ({ getValue }) => (getValue() as string | undefined) ?? '—' },
      { accessorKey: 'gstin', header: 'GSTIN', enableSorting: false,
        cell: ({ getValue }) => (getValue() as string | undefined)
          ? <code className="text-xs">{getValue() as string}</code>
          : '—' },
      { accessorKey: 'is_active', header: 'Active', enableSorting: true,
        cell: ({ getValue }) => (
          <Badge variant={(getValue() as boolean) ? 'default' : 'secondary'}>
            {(getValue() as boolean) ? 'Active' : 'Inactive'}
          </Badge>
        ) },
    ] as ColumnDef<Company, unknown>[] as ColumnDef<Record<string, unknown>, unknown>[],
    useList: useCompanies as unknown as AnyEntityConfig['useList'],
    useDelete: useDeleteCompany as unknown as AnyEntityConfig['useDelete'],
    getId: (row) => (row as unknown as Company).id,
  },
  ports: {
    label: 'Ports',
    searchPlaceholder: 'Search by code or name...',
    columns: [
      { accessorKey: 'port_code', header: 'Code', enableSorting: true,
        cell: ({ getValue }) => <code className="text-xs font-mono">{getValue() as string}</code> },
      { accessorKey: 'port_name', header: 'Name', enableSorting: true },
    ] as ColumnDef<Port, unknown>[] as ColumnDef<Record<string, unknown>, unknown>[],
    useList: usePorts as unknown as AnyEntityConfig['useList'],
    useDelete: useDeletePort as unknown as AnyEntityConfig['useDelete'],
    getId: (row) => (row as unknown as Port).id,
  },
  'hs-codes': {
    label: 'HS Codes',
    searchPlaceholder: 'Search by code or description...',
    columns: [
      { accessorKey: 'hs_code', header: 'HS Code', enableSorting: true,
        cell: ({ getValue }) => <code className="text-xs font-mono">{getValue() as string}</code> },
      { accessorKey: 'description', header: 'Description', enableSorting: false },
    ] as ColumnDef<HSCode, unknown>[] as ColumnDef<Record<string, unknown>, unknown>[],
    useList: useHSCodes as unknown as AnyEntityConfig['useList'],
    useDelete: useDeleteHSCode as unknown as AnyEntityConfig['useDelete'],
    getId: (row) => (row as unknown as HSCode).id,
  },
  'item-groups': {
    label: 'Item Groups',
    searchPlaceholder: 'Search by name...',
    columns: [
      { accessorKey: 'name', header: 'Name', enableSorting: true },
      { accessorKey: 'description', header: 'Description', enableSorting: false,
        cell: ({ getValue }) => (getValue() as string | undefined) ?? '—' },
    ] as ColumnDef<ItemGroup, unknown>[] as ColumnDef<Record<string, unknown>, unknown>[],
    useList: useItemGroups as unknown as AnyEntityConfig['useList'],
    useDelete: useDeleteItemGroup as unknown as AnyEntityConfig['useDelete'],
    getId: (row) => (row as unknown as ItemGroup).id,
  },
  'item-names': {
    label: 'Item Names',
    searchPlaceholder: 'Search by name...',
    columns: [
      { accessorKey: 'name', header: 'Name', enableSorting: true },
      { accessorKey: 'item_group_name', header: 'Group', enableSorting: false,
        cell: ({ getValue }) => (getValue() as string | undefined) ?? '—' },
    ] as ColumnDef<ItemName, unknown>[] as ColumnDef<Record<string, unknown>, unknown>[],
    useList: useItemNames as unknown as AnyEntityConfig['useList'],
    useDelete: useDeleteItemName as unknown as AnyEntityConfig['useDelete'],
    getId: (row) => (row as unknown as ItemName).id,
  },
  'sion-norm-classes': {
    label: 'SION Norm Classes',
    searchPlaceholder: 'Search by norm class...',
    columns: [
      { accessorKey: 'norm_class', header: 'Norm Class', enableSorting: true },
      { accessorKey: 'description', header: 'Description', enableSorting: false,
        cell: ({ getValue }) => (getValue() as string | undefined) ?? '—' },
    ] as ColumnDef<SionNormClass, unknown>[] as ColumnDef<Record<string, unknown>, unknown>[],
    useList: useSionNormClasses as unknown as AnyEntityConfig['useList'],
    useDelete: useDeleteSionNormClass as unknown as AnyEntityConfig['useDelete'],
    getId: (row) => (row as unknown as SionNormClass).id,
  },
  'exchange-rates': {
    label: 'Exchange Rates',
    searchPlaceholder: 'Search by currency...',
    columns: [
      { accessorKey: 'currency', header: 'Currency', enableSorting: true },
      { accessorKey: 'rate', header: 'Rate', enableSorting: true,
        cell: ({ getValue }) => Number(getValue() as string).toFixed(4) },
      { accessorKey: 'date', header: 'Effective Date', enableSorting: true },
    ] as ColumnDef<ExchangeRate, unknown>[] as ColumnDef<Record<string, unknown>, unknown>[],
    useList: useExchangeRates as unknown as AnyEntityConfig['useList'],
    useDelete: useDeleteExchangeRate as unknown as AnyEntityConfig['useDelete'],
    getId: (row) => (row as unknown as ExchangeRate).id,
  },
}

// ─── Page component ───────────────────────────────────────────────────────────

export default function MasterList() {
  const { entity } = useParams<{ entity: string }>()
  const navigate = useNavigate()
  const { isSuperAdmin } = useAuth()

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [ordering, setOrdering] = useState('')

  const config = entity ? ENTITY_CONFIG[entity] : undefined

  // Always call hooks — but only enabled via the guard below.
  const listResult = config?.useList({ search, page, page_size: pageSize, ordering })
  const deleteMutation = config?.useDelete()

  const canWrite = isSuperAdmin()

  const handleDelete = useCallback(
    async (row: Record<string, unknown>) => {
      if (!config || !deleteMutation) return
      if (!window.confirm('Delete this record? This action cannot be undone.')) return
      try {
        await deleteMutation.mutateAsync(config.getId(row))
        toast.success('Record deleted.')
      } catch {
        toast.error('Failed to delete record.')
      }
    },
    [config, deleteMutation],
  )

  const handlePageSizeChange = useCallback((size: number) => {
    setPageSize(size)
    setPage(1)
  }, [])

  const handleSearchChange = useCallback((s: string) => {
    setSearch(s)
    setPage(1)
  }, [])

  if (!config) {
    return (
      <div className="p-8 text-muted-foreground">
        Unknown master entity: <code>{entity}</code>
      </div>
    )
  }

  const data = listResult?.data?.data ?? []
  const totalCount = listResult?.data?.pagination?.count ?? 0
  const isLoading = listResult?.isLoading ?? true
  const isError = listResult?.isError ?? false

  return (
    <div className="flex flex-col gap-4 p-6">
      {/* Page header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <nav className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">
            <Link to="/" className="hover:text-foreground">
              Home
            </Link>
            <span>/</span>
            <span>{config.label}</span>
          </nav>
          <h1 className="text-2xl font-bold">{config.label}</h1>
        </div>
        {canWrite && (
          <Button asChild size="sm">
            <Link to={`/masters/${entity ?? ''}/create`}>
              <Plus className="size-3.5" aria-hidden="true" />
              Add New
            </Link>
          </Button>
        )}
      </div>

      {/* Error state */}
      {isError && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
          Failed to load {config.label.toLowerCase()}. Please try again.
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <MasterDataTable
          columns={config.columns}
          data={data}
          totalCount={totalCount}
          currentPage={page}
          pageSize={pageSize}
          isLoading={isLoading}
          onSearchChange={handleSearchChange}
          onSortChange={(o) => { setOrdering(o); setPage(1); }}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
          canWrite={canWrite}
          onEdit={(row) => navigate(`/masters/${entity ?? ''}/${config.getId(row)}/edit`)}
          onDelete={handleDelete}
          searchPlaceholder={config.searchPlaceholder}
        />
      </div>
    </div>
  )
}
