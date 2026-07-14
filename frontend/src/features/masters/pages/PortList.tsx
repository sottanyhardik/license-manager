// PortList — dedicated route for /masters/ports.

import { useNavigate, Link } from 'react-router-dom'
import { useCallback, useState } from 'react'
import { toast } from 'sonner'
import { Plus } from 'lucide-react'
import type { ColumnDef } from '@tanstack/react-table'
import { useAuth } from '@/shared/auth/AuthContext'
import { Button } from '@/shared/ui/button'
import { MasterDataTable } from '../components/MasterDataTable'
import { usePorts, useDeletePort } from '../queries'
import type { Port } from '../types'

const COLUMNS: ColumnDef<Port, unknown>[] = [
  {
    accessorKey: 'port_code',
    header: 'Code',
    enableSorting: true,
    cell: ({ getValue }) => (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
        {getValue() as string}
      </code>
    ),
  },
  { accessorKey: 'port_name', header: 'Port Name', enableSorting: true },
]

export default function PortList() {
  const navigate = useNavigate()
  const { isSuperAdmin } = useAuth()

  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [ordering, setOrdering] = useState('')

  const { data, isLoading } = usePorts({ search, page, page_size: pageSize, ordering })
  const deleteMutation = useDeletePort()
  const canWrite = isSuperAdmin()

  const handleDelete = useCallback(
    async (row: Port) => {
      if (
        !window.confirm(
          `Delete port "${row.port_name} (${row.port_code})"? This action cannot be undone.`,
        )
      )
        return
      try {
        await deleteMutation.mutateAsync(row.id)
        toast.success('Port deleted.')
      } catch {
        toast.error('Failed to delete port.')
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
            <Link to="/masters/ports" className="hover:text-foreground">
              Ports
            </Link>
          </nav>
          <h1 className="text-2xl font-bold">Ports</h1>
        </div>
        {canWrite && (
          <Button asChild size="sm">
            <Link to="/masters/ports/create">
              <Plus className="size-3.5" aria-hidden="true" />
              Add Port
            </Link>
          </Button>
        )}
      </div>

      <div className="rounded-lg border bg-card p-4 shadow-sm">
        <MasterDataTable<Port>
          columns={COLUMNS}
          data={data?.data ?? []}
          totalCount={data?.pagination?.count ?? 0}
          currentPage={page}
          pageSize={pageSize}
          isLoading={isLoading}
          onSearchChange={handleSearchChange}
          onSortChange={(o) => { setOrdering(o); setPage(1); }}
          onPageChange={setPage}
          onPageSizeChange={handlePageSizeChange}
          canWrite={canWrite}
          onEdit={(row) => navigate(`/masters/ports/${row.id}/edit`)}
          onDelete={handleDelete}
          searchPlaceholder="Search by code or name..."
        />
      </div>
    </div>
  )
}
