// MasterSelect — reusable async selector for any master entity.
//
// Usage:
//   <MasterSelect
//     queryHook={useCompaniesAll}
//     value={selectedId}
//     onChange={(id, item) => { ... }}
//     getLabel={(c) => c.name}
//     placeholder="Select company"
//   />
//
// Design decisions:
//   - Uses a controlled <input> for search + a listbox pattern (no external
//     cmdk/Select dependency beyond Radix primitives already in the bundle).
//   - Loads data from TanStack Query — staleTime is set in the query hook so
//     repeat renders are cache-hit only.
//   - Keyboard accessible: Arrow keys navigate options, Enter selects, Escape
//     closes, Tab moves focus out (closes the listbox).
//   - Shows a loading skeleton row while the query is in flight.

import { useEffect, useId, useRef, useState } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { ChevronDown, X } from 'lucide-react'
import { cn } from '@/shared/utils/cn'
import { Skeleton } from '@/shared/ui/skeleton'

export interface MasterSelectProps<T extends { id: number }> {
  /** TanStack Query hook that returns the full unpaginated list for this master. */
  queryHook: () => UseQueryResult<T[]>
  /** Currently selected id, or null for no selection. */
  value: number | null
  /** Called when the user selects or clears a value. */
  onChange: (id: number | null, item: T | null) => void
  /** Extract a human-readable label from a master item. */
  getLabel: (item: T) => string
  placeholder?: string
  disabled?: boolean
  /** Additional classes applied to the outer wrapper element. */
  className?: string
  /** aria-label for when there is no visible label above the control. */
  'aria-label'?: string
  /** Forward an explicit id for external <label> association. */
  id?: string
}

export function MasterSelect<T extends { id: number }>({
  queryHook,
  value,
  onChange,
  getLabel,
  placeholder = 'Select...',
  disabled = false,
  className,
  'aria-label': ariaLabel,
  id: externalId,
}: MasterSelectProps<T>) {
  const { data: items = [], isLoading } = queryHook()

  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [focusedIndex, setFocusedIndex] = useState(-1)

  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  const autoId = useId()
  const controlId = externalId ?? autoId
  const listId = `${controlId}-listbox`

  const selectedItem = value !== null ? (items.find((i) => i.id === value) ?? null) : null
  const displayLabel = selectedItem ? getLabel(selectedItem) : ''

  const filtered = search.trim()
    ? items.filter((i) => getLabel(i).toLowerCase().includes(search.toLowerCase()))
    : items

  // Close listbox when clicking outside the wrapper.
  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false)
        setSearch('')
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  // Scroll the focused option into view.
  useEffect(() => {
    if (!open || focusedIndex < 0) return
    const li = listRef.current?.children[focusedIndex] as HTMLElement | undefined
    li?.scrollIntoView({ block: 'nearest' })
  }, [focusedIndex, open])

  function openList() {
    if (disabled) return
    setOpen(true)
    setSearch('')
    setFocusedIndex(-1)
    // Focus the search input in the next tick so the list is rendered first.
    requestAnimationFrame(() => inputRef.current?.focus())
  }

  function select(item: T) {
    onChange(item.id, item)
    setOpen(false)
    setSearch('')
  }

  function clear(e: React.MouseEvent) {
    e.stopPropagation()
    onChange(null, null)
    setSearch('')
    setOpen(false)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open) return
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setFocusedIndex((prev) => Math.min(prev + 1, filtered.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setFocusedIndex((prev) => Math.max(prev - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (focusedIndex >= 0 && filtered[focusedIndex]) {
          select(filtered[focusedIndex])
        }
        break
      case 'Escape':
        e.preventDefault()
        setOpen(false)
        setSearch('')
        break
      case 'Tab':
        setOpen(false)
        setSearch('')
        break
    }
  }

  return (
    <div ref={wrapperRef} className={cn('relative', className)}>
      {/* Trigger button — acts as a combobox trigger */}
      <button
        type="button"
        id={controlId}
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listId}
        aria-label={ariaLabel}
        aria-disabled={disabled}
        disabled={disabled}
        onClick={openList}
        className={cn(
          'flex w-full items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm',
          'ring-offset-background transition-colors',
          'hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-50',
          open && 'ring-2 ring-ring ring-offset-2',
        )}
      >
        {isLoading ? (
          <Skeleton className="h-4 w-32" />
        ) : (
          <span className={cn('flex-1 truncate text-left', !displayLabel && 'text-muted-foreground')}>
            {displayLabel || placeholder}
          </span>
        )}
        <span className="ml-auto flex shrink-0 items-center gap-1">
          {value !== null && !disabled && (
            <span
              role="button"
              aria-label="Clear selection"
              tabIndex={0}
              onClick={clear}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') clear(e as unknown as React.MouseEvent)
              }}
              className="rounded p-0.5 hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <X className="size-3.5" aria-hidden="true" />
            </span>
          )}
          <ChevronDown
            className={cn(
              'size-4 text-muted-foreground transition-transform',
              open && 'rotate-180',
            )}
            aria-hidden="true"
          />
        </span>
      </button>

      {/* Dropdown listbox */}
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
          {/* Search input */}
          <div className="border-b p-2">
            <input
              ref={inputRef}
              type="text"
              role="searchbox"
              aria-label="Search options"
              aria-controls={listId}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setFocusedIndex(-1)
              }}
              onKeyDown={handleKeyDown}
              placeholder="Search..."
              className={cn(
                'w-full rounded-sm border-0 bg-transparent px-1 py-0.5 text-sm',
                'placeholder:text-muted-foreground focus:outline-none',
              )}
            />
          </div>

          {/* Options list */}
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            aria-label={placeholder}
            className="max-h-60 overflow-y-auto p-1"
          >
            {isLoading ? (
              <li className="flex flex-col gap-1.5 p-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-5 w-full" />
                ))}
              </li>
            ) : filtered.length === 0 ? (
              <li className="px-2 py-3 text-center text-sm text-muted-foreground">
                No results found.
              </li>
            ) : (
              filtered.map((item, idx) => {
                const isSelected = item.id === value
                const isFocused = idx === focusedIndex
                return (
                  <li
                    key={item.id}
                    role="option"
                    aria-selected={isSelected}
                    onMouseEnter={() => setFocusedIndex(idx)}
                    onMouseDown={(e) => {
                      // Prevent blur on the search input before click fires.
                      e.preventDefault()
                      select(item)
                    }}
                    className={cn(
                      'cursor-pointer rounded-sm px-2 py-1.5 text-sm',
                      isFocused && 'bg-accent text-accent-foreground',
                      isSelected && !isFocused && 'font-semibold text-primary',
                    )}
                  >
                    {getLabel(item)}
                  </li>
                )
              })
            )}
          </ul>
        </div>
      )}
    </div>
  )
}
