// CompanyList — dedicated route for /masters/companies.
// Renders the generic MasterList pre-bound to the "companies" entity.
// Having a named lazy import keeps the bundle chunk readable and allows
// future company-specific customisation without touching MasterList.

import { useNavigate, Link } from 'react-router-dom'
import { useCallback, useState } from 'react'
import { toast } from 'sonner'
import { Plus } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'
import { useAuth } from '@/shared/auth/AuthContext'
import { Button } from '@/shared/ui/button'
import { Badge } from '@/shared/ui/badge'
import { MasterDataTable } from '../components/MasterDataTable'
import { useCompanies, useDeleteCompany } from '../queries'
import type { Company } from '../types'

const COLUMNS: ColumnDef<Company, unknown>[] = [
  { accessorKey: 'name', header: 'Name', enableSorting: true },
  {
    accessorKey: 'city',
    header: 'City',
    enableSorting: true,
    cell: ({ getValue }) => (getValue() as string | undefined) ?? '—',
  },
  {
    accessorKey: 'state',
    header: 'State',
    enableSorting: false,
    cell: ({ getValue }) => (getValue() as string | undefined) ?? '—',
  },
  {
    accessorKey: 'gstin',
    header: 'GSTIN',
    enableSorting: false,
    cell: ({ getValue }) => {
      const val = getValue() as string | undefined
      return val ? <code className="text-xs">{val}</code> : '—'
    },
  },
  {
    accessorKey: 'is_active',
    header: 'Status',
    enableSorting: true,
    cell: ({ getValue }) => (
      <Badge variant={(getValue() as boolean) ? 'default' : 'secondary'}>
        {(getValue() as boolean) ? 'Active' : 'Inactive'}
      </Badge>
    ),
  },
]

export default function CompanyList() {
  const navigate = useNavigate()
  const { isSuperAdmin } = useAuth()

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [ordering, setOrdering] = useState('')

  const { data, isLoading } = useCompanies({ search, page, page_size: pageSize, ordering })
  const deleteMutation = useDeleteCompany()
  const canWrite = isSuperAdmin()

  const handleDelete = useCallback(
    async (row: Company) => {
      if (!window.confirm(`Delete company "${row.name}"? This action cannot be undone.`)) return
      try {
        await deleteMutation.mutateAsync(row.id)
        toast.success('Company deleted.')
      } catch {
        toast.error('Failed to delete company.')
      }
    },
    [deleteMutation],
  )

  const handlePageSizeChange = useCallback((size: number) => {
    setPageSize(size)
    setPage(1)
  }, [])

  const handleSearchChange = useCallback((s: string) => {
    setSearch(s)
    setPage(1)
  }, [])

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <nav className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">
            <Link to="/" className="hover:text-foreground">
              Home
            </Link>
            <span>/</span>
            <Link to="/masters/companies" className="hover:text-foreground">
              Companies
            </Link>
          </nav>
          <h1 className="text-2xl font-bold">Companies</h1>
        </div>
        {canWrite && (
          <Button asChild size="sm">
            <Link to="/masters/companies/create">
              <Plus className="size-3.5" aria-hidden="true" />
              Add Company
            </Link>
          </Button>
        )}
      </div>

      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <MasterDataTable<Company>
          columns={COLUMNS}
          data={data?.results ?? []}
          totalCount={data?.count ?? 0}
          currentPage={page}
          pageSize={pageSize}
          isLoading={isLoading}
          onSearchChange={handleSearchChange}
          onSortChange={(o) => { setOrdering(o); setPage(1); }}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
          canWrite={canWrite}
          onEdit={(row) => navigate(`/masters/companies/${row.id}/edit`)}
          onDelete={handleDelete}
          searchPlaceholder="Search by name, city, GSTIN..."
        />
      </div>
    </div>
  )
}
