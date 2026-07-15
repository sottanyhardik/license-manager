/**
 * UserList — paginated list of all users for admin/USER_MANAGER.
 *
 * Features:
 *   - Table: username (+ Super Admin badge), email, roles, status, edit/delete actions
 *   - Search by username/email/first_name/last_name (debounced 350 ms)
 *   - Filter by role and is_active (native selects)
 *   - Create → /admin/users/new
 *   - Edit   → /admin/users/:id/edit
 *   - Delete: superuser-only, Radix confirm dialog
 */

import { useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'
import { toast } from 'sonner'
import { Pencil, Plus, Search, Trash2, Users } from 'lucide-react'

import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { AuthContext } from '@/shared/auth/AuthContext'
import { ROLE_LABELS, ROLES } from '@/shared/auth/roles'
import { ROUTES } from '@/shared/routes'
import { Badge } from '@/shared/ui/badge'
import { Button } from '@/shared/ui/button'
import { Card, CardContent } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { cn } from '@/shared/utils/cn'

import type { ManagedUser } from '../types'

export default function UserList() {
  const navigate = useNavigate()
  const { user: currentUser } = useContext(AuthContext)

  const [users, setUsers] = useState<ManagedUser[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<ManagedUser | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Debounce search — only fire after 350 ms of no typing.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 350)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search])

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (debouncedSearch) params.search = debouncedSearch
      if (roleFilter) params.role = roleFilter
      if (activeFilter) params.is_active = activeFilter
      const { data } = await apiClient.get<ManagedUser[]>(ENDPOINTS.USERS.LIST, { params })
      setUsers(Array.isArray(data) ? data : [])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load users'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, roleFilter, activeFilter])

  useEffect(() => {
    void fetchUsers()
  }, [fetchUsers])

  const handleDelete = async () => {
    if (!confirmDelete) return
    setDeleting(true)
    try {
      await apiClient.delete(ENDPOINTS.USERS.DETAIL(confirmDelete.id))
      toast.success('User deleted')
      setConfirmDelete(null)
      void fetchUsers()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete user'
      toast.error(msg)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      {/* Page header */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Admin
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">User Management</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">Manage users, roles and access</p>
        </div>
        <Button onClick={() => navigate(ROUTES.ADMIN.USER_NEW)}>
          <Plus className="size-4" />
          Add User
        </Button>
      </div>

      {/* Filters */}
      <Card className="mb-3">
        <CardContent className="flex flex-wrap items-center gap-2 py-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="h-9 pl-8"
              placeholder="Search by username or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {/* Role filter */}
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className={cn(
              'h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground',
              'focus:outline-none focus:ring-2 focus:ring-ring',
            )}
          >
            <option value="">All Roles</option>
            {Object.values(ROLES).map((code) => (
              <option key={code} value={code}>
                {ROLE_LABELS[code] ?? code}
              </option>
            ))}
          </select>
          {/* Active status filter */}
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
            className={cn(
              'h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground',
              'focus:outline-none focus:ring-2 focus:ring-ring',
            )}
          >
            <option value="">All Status</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-sm text-muted-foreground">Loading users…</div>
          ) : users.length === 0 ? (
            <div className="flex flex-col items-center gap-2 p-10 text-center text-muted-foreground">
              <Users className="size-8 opacity-50" />
              <span className="text-sm">No users found.</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2.5">User</th>
                    <th className="px-4 py-2.5">Email</th>
                    <th className="px-4 py-2.5">Roles</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr
                      key={u.id}
                      className="border-b border-border/60 transition-colors hover:bg-accent/40"
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1.5 font-medium text-foreground">
                          {u.username}
                          {u.is_superuser && (
                            <Badge variant="destructive" className="text-[11px]">
                              Super Admin
                            </Badge>
                          )}
                        </div>
                        {(u.first_name || u.last_name) && (
                          <div className="text-xs text-muted-foreground">
                            {u.first_name} {u.last_name}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{u.email || '—'}</td>
                      <td className="px-4 py-2.5">
                        {(u.roles ?? []).length === 0 ? (
                          <span className="text-xs text-muted-foreground">No roles</span>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {(u.roles ?? []).map((r) => (
                              <Badge key={r} variant="secondary" className="text-[11px]">
                                {ROLE_LABELS[r] ?? r}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <Badge variant={u.is_active ? 'default' : 'secondary'}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex justify-end gap-1.5">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(ROUTES.ADMIN.USER_EDIT(u.id))}
                          >
                            <Pencil className="size-3.5" />
                            Edit
                          </Button>
                          {currentUser?.is_superuser && u.id !== currentUser?.id && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-destructive hover:bg-destructive/10"
                              onClick={() => setConfirmDelete(u)}
                            >
                              <Trash2 className="size-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation — Radix Dialog */}
      <Dialog.Root open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-background p-6 shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
            <Dialog.Title className="text-base font-semibold text-foreground">
              Delete User
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-muted-foreground">
              Are you sure you want to delete{' '}
              <strong className="text-foreground">{confirmDelete?.username}</strong>? This cannot
              be undone.
            </Dialog.Description>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setConfirmDelete(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={deleting}
                onClick={() => void handleDelete()}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}
