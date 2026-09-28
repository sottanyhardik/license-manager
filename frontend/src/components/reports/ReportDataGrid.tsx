import React, { useMemo } from 'react';
import {
  DataGrid,
  GridColDef,
} from '@mui/x-data-grid';
import { Box, Paper, useTheme } from '@mui/material';
import { Loader2 } from 'lucide-react';

export interface ReportDataGridProps {
  rows: any[];
  columns: GridColDef[];
  loading?: boolean;
  onRowClick?: (id: any) => void;
  pageSize?: number;
  disableRowSelectionOnClick?: boolean;
  density?: 'compact' | 'standard' | 'comfortable';
  totalRows?: number;
  totalsRow?: any;
  height?: number | string;
  showTotals?: boolean;
  sx?: any;
}

/**
 * Reusable DataGrid component for all report pages
 * Handles:
 * - Standardized styling (light/dark mode)
 * - Sortable columns
 * - Pagination
 * - Custom row/cell rendering
 * - Totals row support
 */
export default function ReportDataGrid({
  rows,
  columns,
  loading = false,
  onRowClick,
  pageSize = 25,
  disableRowSelectionOnClick = true,
  density = 'compact',
  height = 600,
  showTotals = false,
  totalsRow = null,
  sx = {},
}: ReportDataGridProps) {
  const theme = useTheme();

  const enhancedColumns = useMemo(() => {
    return columns.map(col => ({
      ...col,
      // Ensure all columns are sortable by default
      sortable: col.sortable !== false,
      // Add consistent styling
      headerAlign: col.headerAlign || 'left',
      align: col.align || 'left',
    }));
  }, [columns]);

  const displayRows = useMemo(() => {
    if (!showTotals || !totalsRow) {
      return rows;
    }
    // Add totals row at the end with special ID
    return [
      ...rows,
      {
        id: '__TOTALS_ROW__',
        ...totalsRow,
      },
    ];
  }, [rows, showTotals, totalsRow]);

  return (
    <Paper
      elevation={0}
      sx={{
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 1,
        overflow: 'auto',
        ...sx,
      }}
    >
      {loading && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 300,
            gap: 1,
            color: 'text.secondary',
          }}
        >
          <Loader2 className="size-5 animate-spin" />
          <span>Loading report data...</span>
        </Box>
      )}

      {!loading && displayRows.length === 0 && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 300,
            color: 'text.secondary',
          }}
        >
          No data available
        </Box>
      )}

      {!loading && displayRows.length > 0 && (
        <DataGrid
          rows={displayRows as any[]}
          columns={enhancedColumns as any}
          density={density}
          disableRowSelectionOnClick={disableRowSelectionOnClick}
          onRowClick={onRowClick ? (params: any) => onRowClick(params.id) : undefined}
          initialState={{
            pagination: {
              paginationModel: { pageSize, page: 0 },
            },
          } as any}
          pageSizeOptions={[10, 25, 50, 100]}
          slotProps={{
            loadingOverlay: {
              variant: 'skeleton',
              noRowsVariant: 'skeleton',
            } as any,
          } as any}
          sx={{
            height,
            '& .MuiDataGrid-root': {
              border: 'none',
              backgroundColor: 'transparent',
            },
            '& .MuiDataGrid-cell': {
              borderBottomColor: theme.palette.divider,
              fontSize: '0.875rem',
            },
            '& .MuiDataGrid-columnHeader': {
              backgroundColor: theme.palette.mode === 'light'
                ? theme.palette.grey[50]
                : theme.palette.grey[900],
              borderBottomColor: theme.palette.divider,
              fontSize: '0.875rem',
              fontWeight: 600,
            },
            '& .MuiDataGrid-row': {
              '&:hover': {
                backgroundColor: theme.palette.action.hover,
              },
              '&.Mui-selected': {
                backgroundColor: theme.palette.action.selected,
              },
            },
            // Totals row styling
            '& .MuiDataGrid-row[data-id="__TOTALS_ROW__"]': {
              backgroundColor: theme.palette.mode === 'light'
                ? theme.palette.grey[100]
                : theme.palette.grey[800],
              fontWeight: 600,
              borderTopWidth: 2,
              borderTopColor: theme.palette.divider,
              '&:hover': {
                backgroundColor: theme.palette.mode === 'light'
                  ? theme.palette.grey[100]
                  : theme.palette.grey[800],
              },
            },
          } as any}
        />
      )}
    </Paper>
  );
}
