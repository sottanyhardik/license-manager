/**
 * MUI DataGrid Wrapper Component
 * Replaces DataTable.tsx with MUI X DataGrid
 * Supports: inline editing, boolean toggles, custom cell renderers, actions, pagination, filtering, sorting
 */

import React, { useState, useCallback, useMemo, ElementType } from 'react';
import {
  DataGrid,
  GridColDef,
  GridRenderCellParams,
  GridPaginationModel,
  GridSortModel,
  GridFilterModel,
} from '@mui/x-data-grid';
import { Box, LinearProgress, useTheme } from '@mui/material';
import { toast } from 'sonner';
import { Pencil, Trash2, Eye, FileText, ArrowLeftRight, Copy, Download, Check, LogIn, X, Inbox } from 'lucide-react';
import Icon from '@/components/Icon';
import { formatDate } from '@/utils/dateFormatter';
import { cn } from '@/lib/utils';

// Resolve action icon names
const ACTION_ICONS: Record<string, ElementType> = {
  FileText,
  ArrowLeftRight,
  Eye,
  Pencil,
  Copy,
  LogIn,
  Download,
  Trash2,
  Check,
};

function ActionIcon({ name }: { name: string }) {
  const L = ACTION_ICONS[name];
  return L ? <L className="size-4" aria-hidden="true" /> : <Icon name={name} className="size-4" />;
}

// Numeric column detection
const NUMERIC_PATTERNS = [
  'amount',
  'price',
  'rate',
  'cost',
  'total',
  'subtotal',
  'quantity',
  'qty',
  'weight',
  'count',
  'number',
  'inr',
  'usd',
  'fc',
  'cif',
  'fob',
  'paid',
  'due',
  'balance',
  'pct',
  'percent',
  'exc_rate',
];

function isNumericColumn(col: string): boolean {
  const lower = col.toLowerCase();
  return NUMERIC_PATTERNS.some((p) => lower.includes(p));
}

function formatColumnName(col: string): string {
  return col.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface MuiDataGridProps {
  data?: any[];
  columns?: string[];
  onEdit?: (item: any) => void;
  onDelete?: (item: any) => void;
  customActions?: Array<{
    label: string;
    icon?: string;
    onClick: (item: any) => void;
    className?: string;
    showIf?: (item: any) => boolean;
  }>;
  loading?: boolean;
  inlineEditable?: string[];
  onInlineUpdate?: (id: any, columnName: string, value: any) => Promise<void>;
  customCellRender?: Record<string, (item: any, value: any) => React.ReactNode>;
  getRowStyle?: (item: any) => React.CSSProperties;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  currentPage?: number;
  onPageChange?: (page: number) => void;
  totalRows?: number;
  onSort?: (sortModel: GridSortModel) => void;
  onFilter?: (filterModel: GridFilterModel) => void;
  paginationModel?: GridPaginationModel;
  onPaginationModelChange?: (model: GridPaginationModel) => void;
  sortModel?: GridSortModel;
  filterModel?: GridFilterModel;
}

export default function MuiDataGrid({
  data = [],
  columns = [],
  onEdit,
  onDelete,
  customActions = [],
  loading = false,
  inlineEditable = [],
  onInlineUpdate,
  customCellRender = {},
  getRowStyle = null,
  pageSize = 25,
  onPageSizeChange,
  currentPage = 1,
  onPageChange,
  totalRows = 0,
  onSort,
  onFilter,
  paginationModel,
  onPaginationModelChange,
  sortModel,
  filterModel,
}: MuiDataGridProps) {
  const theme = useTheme();
  const [editingCell, setEditingCell] = useState<{ rowId: any; columnName: string } | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);

  const formatValue = useCallback(
    (value: any, columnName: string, isEditableField: boolean = false): React.ReactNode => {
      if (value === null || value === undefined) {
        return <span className="text-muted-foreground">—</span>;
      }
      if (typeof value === 'boolean') {
        if (isEditableField) {
          return (
            <label className="inline-flex cursor-pointer items-center">
              <input
                type="checkbox"
                role="switch"
                checked={value}
                onChange={() => {}}
                aria-label="Toggle"
                className="sr-only peer"
              />
              <span
                aria-hidden="true"
                className={cn(
                  'relative inline-block h-5 w-9 rounded-full border transition-colors duration-200',
                  value ? 'border-primary/30 bg-primary' : 'border-border bg-muted',
                )}
              >
                <span
                  className={cn(
                    'absolute top-0.5 size-4 rounded-full bg-white shadow-sm transition-transform duration-200',
                    value ? 'translate-x-4' : 'translate-x-0.5',
                  )}
                />
              </span>
            </label>
          );
        }
        return value ? (
          <span className="inline-flex items-center rounded-md border border-success/20 bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
            Yes
          </span>
        ) : (
          <span className="inline-flex items-center rounded-md border border-border bg-muted/60 px-2 py-0.5 text-xs font-medium text-muted-foreground">
            No
          </span>
        );
      }
      if (columnName && (columnName.includes('date') || columnName.includes('_at') || columnName.includes('_on'))) {
        const formatted = formatDate(value);
        if (formatted) return formatted;
      }
      if (typeof value === 'object') return JSON.stringify(value);
      return String(value);
    },
    [],
  );

  const handleCellClick = useCallback(
    (item: any, columnName: string) => {
      if (inlineEditable.includes(columnName)) {
        setEditingCell({ rowId: item.id, columnName });
        setEditValue(item[columnName] || '');
      }
    },
    [inlineEditable],
  );

  const handleSave = useCallback(
    async (item: any, columnName: string) => {
      if (!onInlineUpdate) return;
      setSaving(true);
      try {
        await onInlineUpdate(item.id, columnName, editValue);
        setEditingCell(null);
      } catch (error: any) {
        toast.error(error?.response?.data?.error || 'Failed to save. Please try again.');
      } finally {
        setSaving(false);
      }
    },
    [onInlineUpdate],
  );

  const handleCancel = useCallback(() => {
    setEditingCell(null);
    setEditValue('');
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, item: any, columnName: string) => {
      if (e.key === 'Enter') handleSave(item, columnName);
      else if (e.key === 'Escape') handleCancel();
    },
    [handleSave, handleCancel],
  );

  const isEditing = useCallback(
    (item: any, columnName: string) => editingCell?.rowId === item.id && editingCell?.columnName === columnName,
    [editingCell],
  );

  const handleBooleanToggle = useCallback(
    async (item: any, columnName: string, currentValue: boolean) => {
      setSaving(true);
      try {
        await onInlineUpdate?.(item.id, columnName, !currentValue);
      } catch (error: any) {
        toast.error(error?.response?.data?.error || 'Failed to update.');
      } finally {
        setSaving(false);
      }
    },
    [onInlineUpdate],
  );

  // Build column definitions for MUI DataGrid
  const gridColumns = useMemo<GridColDef[]>(() => {
    const cols: GridColDef[] = columns.map((col) => {
      const isNumeric = isNumericColumn(col);

      return {
        field: col,
        headerName: formatColumnName(col),
        flex: 1,
        minWidth: 100,
        align: isNumeric ? 'right' : 'left',
        headerAlign: isNumeric ? 'right' : 'left',
        sortable: true,
        filterable: true,
        editable: false,
        renderCell: (params: GridRenderCellParams) => {
          const item = params.row;
          const value = item[col];
          const isCurrentlyEditing = isEditing(item, col);
          const isEditable = inlineEditable.includes(col);

          // Editing mode
          if (isCurrentlyEditing) {
            return (
              <div className="flex items-center gap-1">
                <input
                  type="text"
                  className="flex h-8 min-w-[80px] rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => handleKeyDown(e, item, col)}
                  onBlur={() => handleSave(item, col)}
                  autoFocus
                  disabled={saving}
                />
                <button
                  className="flex items-center justify-center rounded px-[7px] py-[2px] text-xs bg-success text-white cursor-pointer hover:bg-success/90"
                  onClick={() => handleSave(item, col)}
                  disabled={saving}
                  title="Save"
                >
                  <Check className="size-4" aria-hidden="true" />
                </button>
                <button
                  className="flex items-center justify-center rounded border border-border bg-card px-[7px] py-[2px] text-xs text-muted-foreground cursor-pointer hover:bg-muted"
                  onClick={handleCancel}
                  disabled={saving}
                  title="Cancel"
                >
                  <X className="size-4" aria-hidden="true" />
                </button>
              </div>
            );
          }

          // Display mode
          const content = customCellRender[col] ? customCellRender[col](item, value) : formatValue(value, col, isEditable);

          return (
            <span
              className={
                isEditable && typeof value !== 'boolean' ? 'group/cell relative inline-flex items-center gap-1.5 rounded pr-1 cursor-pointer' : ''
              }
              onClick={() => {
                if (!isCurrentlyEditing && isEditable && typeof value === 'boolean') {
                  handleBooleanToggle(item, col, value);
                } else if (!isCurrentlyEditing && isEditable) {
                  handleCellClick(item, col);
                }
              }}
              title={
                isEditable && typeof value === 'boolean' ? 'Click to toggle' : isEditable ? 'Click to edit' : ''
              }
            >
              {content}
              {isEditable && typeof value !== 'boolean' && (
                <Pencil className="size-3 shrink-0 text-muted-foreground/40 opacity-0 transition-opacity duration-150 group-hover/cell:opacity-100" />
              )}
            </span>
          );
        },
      };
    });

    // Add actions column if there are any actions
    if (onEdit || onDelete || customActions.length > 0) {
      cols.push({
        field: 'actions',
        headerName: 'Actions',
        type: 'actions',
        width: 120,
        align: 'center',
        sortable: false,
        filterable: false,
        renderCell: (params: GridRenderCellParams) => {
          const item = params.row;
          return (
            <div className="inline-flex items-center gap-1">
              {customActions.map((action, idx) => {
                if (action.showIf && !action.showIf(item)) return null;
                return (
                  <button
                    key={`custom-${idx}`}
                    className={action.className || 'inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted'}
                    onClick={() => action.onClick(item)}
                    title={action.label}
                    aria-label={action.label}
                  >
                    {action.icon && <ActionIcon name={action.icon} />}
                  </button>
                );
              })}
              {onEdit && (
                <button
                  className="inline-flex size-7 items-center justify-center rounded-md border border-primary/25 bg-primary/5 text-primary transition-colors hover:bg-primary/12 hover:border-primary/40 cursor-pointer"
                  onClick={() => onEdit(item)}
                  title="Edit"
                  aria-label={`Edit ${item.id || 'record'}`}
                >
                  <Pencil className="size-3.5" aria-hidden="true" />
                </button>
              )}
              {onDelete && (
                <button
                  className="inline-flex size-7 items-center justify-center rounded-md border border-destructive/25 bg-destructive/5 text-destructive transition-colors hover:bg-destructive/12 hover:border-destructive/40 cursor-pointer"
                  onClick={() => onDelete(item)}
                  title="Delete"
                  aria-label={`Delete ${item.id || 'record'}`}
                >
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </button>
              )}
            </div>
          );
        },
      });
    }

    return cols;
  }, [columns, customActions, onEdit, onDelete, inlineEditable, customCellRender, formatValue, handleCellClick, isEditing, editValue, editingCell, saving, handleSave, handleCancel, handleKeyDown, handleBooleanToggle]);

  // Handle pagination
  const paginationModelLocal = paginationModel || {
    pageSize: pageSize || 25,
    page: (currentPage || 1) - 1, // MUI uses 0-based indexing
  };

  const handlePaginationChange = useCallback(
    (newModel: GridPaginationModel) => {
      if (onPaginationModelChange) {
        onPaginationModelChange(newModel);
      } else {
        onPageChange?.(newModel.page + 1); // Convert to 1-based
        onPageSizeChange?.(newModel.pageSize);
      }
    },
    [onPaginationModelChange, onPageChange, onPageSizeChange],
  );

  // Handle sorting
  const handleSortModelChange = useCallback(
    (newSortModel: GridSortModel) => {
      onSort?.(newSortModel);
    },
    [onSort],
  );

  // Handle filtering
  const handleFilterModelChange = useCallback(
    (newFilterModel: GridFilterModel) => {
      onFilter?.(newFilterModel);
    },
    [onFilter],
  );

  // Empty state
  if (!loading && data.length === 0) {
    return (
      <div className="flex flex-col items-center px-6 py-14 text-center">
        <span className="mb-3 flex size-12 items-center justify-center rounded-xl border border-border/60 bg-muted/50">
          <Inbox className="size-5 text-muted-foreground/50" aria-hidden="true" />
        </span>
        <p className="text-sm font-semibold text-foreground">No records found</p>
        <p className="mt-1 text-xs text-muted-foreground">Try adjusting your search or filter criteria</p>
      </div>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      {loading && <LinearProgress />}
      <Box
        sx={{
          '& .MuiDataGrid-root': {
            border: `1px solid ${theme.palette.divider}`,
            backgroundColor: theme.palette.background.paper,
            borderRadius: theme.shape.borderRadius,
          },
          '& .MuiDataGrid-cell': {
            borderColor: theme.palette.divider,
            py: 1,
            px: 1.5,
          },
          '& .MuiDataGrid-columnHeader': {
            backgroundColor: theme.palette.mode === 'dark' ? theme.palette.grey[900] : theme.palette.grey[100],
            borderColor: theme.palette.divider,
            fontWeight: 600,
          },
          '& .MuiDataGrid-row': {
            '&:hover': {
              backgroundColor: theme.palette.action.hover,
            },
          },
          '& .MuiTablePagination-root': {
            borderTop: `1px solid ${theme.palette.divider}`,
          },
        }}
      >
        <DataGrid
          rows={data}
          columns={gridColumns}
          pageSizeOptions={[10, 25, 50, 100, 200]}
          paginationModel={paginationModelLocal}
          onPaginationModelChange={handlePaginationChange}
          rowCount={totalRows || data.length}
          paginationMode={totalRows > 0 ? 'server' : 'client'}
          sortModel={sortModel}
          onSortModelChange={handleSortModelChange}
          filterModel={filterModel}
          onFilterModelChange={handleFilterModelChange}
          loading={loading}
          getRowId={(row) => row.id || Math.random()}
          disableRowSelectionOnClick
          sx={{
            boxShadow: 'none',
            '& .MuiDataGrid-cell:focus, & .MuiDataGrid-cell:focus-within': {
              outline: 'none',
            },
            '& .MuiDataGrid-columnHeader:focus, & .MuiDataGrid-columnHeader:focus-within': {
              outline: 'none',
            },
          }}
        />
      </Box>
    </Box>
  );
}
