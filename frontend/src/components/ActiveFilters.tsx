import React from 'react';
import { X, XCircle, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

/**
 * Represents a single active filter to display
 */
export interface ActiveFilterItem {
  /** Unique key for the filter (used for removal) */
  key: string;
  /** Human-readable label (e.g., "License Status") */
  label: string;
  /** Display value or count (e.g., "Active" or "5 companies") */
  value: string | number;
  /** Optional badge variant */
  variant?: 'default' | 'secondary' | 'info' | 'success' | 'warning' | 'destructive';
}

export interface ActiveFiltersProps {
  /** Array of active filters to display */
  filters: ActiveFilterItem[];
  /** Callback when individual filter's remove button clicked */
  onRemove?: (key: string) => void;
  /** Callback when Clear All clicked */
  onClearAll?: () => void;
  /** Show count of active filters in header */
  showCount?: boolean;
  /** Custom CSS class */
  className?: string;
  /** Whether to display as a compact row or expandable section */
  compact?: boolean;
  /** Position in the UI (default, inline, header) */
  position?: 'default' | 'inline' | 'header';
}

/**
 * ActiveFilters component — displays all active filters with individual remove buttons
 * and a Clear All action. Shows human-readable filter names and values.
 *
 * Usage:
 * ```tsx
 * const activeFilters = [
 *   { key: 'status', label: 'License Status', value: 'Active' },
 *   { key: 'companies', label: 'Companies', value: '3 selected' },
 * ];
 *
 * <ActiveFilters
 *   filters={activeFilters}
 *   onRemove={(key) => removeFilter(key)}
 *   onClearAll={() => clearAllFilters()}
 * />
 * ```
 */
export default function ActiveFilters({
  filters,
  onRemove,
  onClearAll,
  showCount = true,
  className,
  compact = false,
}: ActiveFiltersProps) {
  if (!filters || filters.length === 0) {
    return null;
  }

  const count = filters.length;

  if (compact) {
    // Compact single-line display with chip badges
    return (
      <div
        className={cn(
          'flex flex-wrap items-center gap-2 rounded-lg bg-blue-50 dark:bg-blue-950/30 px-3 py-2 border border-blue-200 dark:border-blue-800',
          className,
        )}
        role="region"
        aria-label="Active filters"
      >
        <Filter className="size-4 text-blue-600 dark:text-blue-400" aria-hidden="true" />
        <div className="flex flex-wrap gap-2 flex-1">
          {filters.map((filter) => (
            <Badge
              key={filter.key}
              variant={filter.variant || 'secondary'}
              className="flex items-center gap-1.5 px-2.5 py-1"
            >
              <span className="text-xs font-medium">
                {filter.label}: {filter.value}
              </span>
              {onRemove && (
                <button
                  onClick={() => onRemove(filter.key)}
                  className="ml-1 inline-flex items-center rounded hover:bg-black/10 dark:hover:bg-white/10 p-0.5"
                  title={`Remove ${filter.label} filter`}
                  aria-label={`Remove ${filter.label} filter`}
                >
                  <X className="size-3" aria-hidden="true" />
                </button>
              )}
            </Badge>
          ))}
        </div>
        {onClearAll && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onClearAll}
            className="h-8 px-3 text-xs"
            title="Clear all filters"
          >
            <XCircle className="size-4 mr-1.5" aria-hidden="true" />
            Clear All
          </Button>
        )}
      </div>
    );
  }

  // Standard display with organized layout
  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-muted/40 p-3 space-y-2',
        className,
      )}
      role="region"
      aria-label="Active filters"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-foreground">
            Active Filters
            {showCount && <span className="ml-2 text-xs font-normal text-muted-foreground">({count})</span>}
          </h3>
        </div>
        {onClearAll && (
          <Button
            variant="outline"
            size="sm"
            onClick={onClearAll}
            className="h-8 px-3 text-xs"
            title="Clear all filters"
          >
            <XCircle className="size-4 mr-1.5" aria-hidden="true" />
            Clear All
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {filters.map((filter) => (
          <div
            key={filter.key}
            className="flex items-center gap-1.5 rounded-md bg-background px-2.5 py-1.5 border border-border"
          >
            <div className="flex flex-col gap-0.5">
              <span className="text-xs font-medium text-muted-foreground">{filter.label}</span>
              <span className="text-sm font-semibold text-foreground">{filter.value}</span>
            </div>
            {onRemove && (
              <button
                onClick={() => onRemove(filter.key)}
                className="ml-1.5 inline-flex items-center rounded hover:bg-muted p-1"
                title={`Remove ${filter.label} filter`}
                aria-label={`Remove ${filter.label} filter: ${filter.value}`}
              >
                <X className="size-4 text-muted-foreground hover:text-foreground" aria-hidden="true" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

