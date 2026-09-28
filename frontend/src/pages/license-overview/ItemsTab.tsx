import { useMemo } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { DataGrid, GridColDef } from "@mui/x-data-grid";
import { Box, useTheme } from "@mui/material";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useLicenseOverviewItems } from "./useLicenseOverviewItems";
import { extractApiError, fmtNum } from "./licenseOverviewHelpers";
import type { LicenseOverviewItemRow } from "./types";

interface ItemsTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

type SortKey = keyof LicenseOverviewItemRow;

/**
 * Items tab — one row per import item's balance breakdown, from
 * `GET /licenses/<id>/overview-items/`. `balance_qty`/`balance_cif` here are
 * a NEW, display-only figure (`total - debited - allotted`) that is
 * intentionally distinct from the "available"/"balance" figures shown
 * elsewhere (e.g. the license accordion row) — see `types.ts`.
 *
 * Now uses MUI DataGrid for consistent table styling and sorting.
 */
export default function ItemsTab({ licenseId, isActive }: ItemsTabProps) {
    const { data, isLoading, isError, error } = useLicenseOverviewItems(licenseId, isActive);
    const theme = useTheme();

    const footerTotals = data?.footer_totals;

    // Transform rows for DataGrid (add totals row at end if needed)
    const rows = useMemo(() => {
        const baseRows = data?.rows ?? [];
        // Add totals row with special ID
        if (footerTotals) {
            return [
                ...baseRows,
                {
                    id: '__TOTALS_ROW__',
                    description: 'Total',
                    hs_code: '',
                    unit: '',
                    total_qty: footerTotals.total_qty ?? 0,
                    total_cif: footerTotals.total_cif ?? 0,
                    debited_qty: footerTotals.debited_qty ?? 0,
                    debited_cif: footerTotals.debited_cif ?? 0,
                    allotted_qty: footerTotals.allotted_qty ?? 0,
                    allotted_cif: footerTotals.allotted_cif ?? 0,
                    balance_qty: footerTotals.balance_qty ?? 0,
                    effective_balance_cif: footerTotals.actual_effective_balance_cif ?? footerTotals.balance_cif ?? 0,
                } as unknown as LicenseOverviewItemRow,
            ];
        }
        return baseRows;
    }, [data?.rows, footerTotals]);

    const columns = useMemo<GridColDef[]>(() => [
        {
            field: 'description',
            headerName: 'Product Description',
            flex: 1.5,
            minWidth: 200,
            sortable: true,
            renderCell: (params) => {
                const value = params.value as string | null | undefined;
                return (
                    <div
                        className={
                            params.row.id === '__TOTALS_ROW__'
                                ? 'font-semibold'
                                : 'truncate'
                        }
                        title={value ?? ''}
                    >
                        {value ?? '—'}
                    </div>
                );
            },
        },
        {
            field: 'hs_code',
            headerName: 'HSN Code',
            width: 120,
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {(params.value as string | null) ?? '—'}
                </span>
            ),
        },
        {
            field: 'unit',
            headerName: 'Unit',
            width: 100,
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {(params.value as string | null) ?? '—'}
                </span>
            ),
        },
        {
            field: 'total_qty',
            headerName: 'Total Qty',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {fmtNum(params.value as number)}
                </span>
            ),
        },
        {
            field: 'total_cif',
            headerName: 'Total CIF',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {fmtNum(params.value as number)}
                </span>
            ),
        },
        {
            field: 'debited_qty',
            headerName: 'Debited Qty',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {fmtNum(params.value as number)}
                </span>
            ),
        },
        {
            field: 'debited_cif',
            headerName: 'Debited CIF',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {fmtNum(params.value as number)}
                </span>
            ),
        },
        {
            field: 'allotted_qty',
            headerName: 'Allotted Qty',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {fmtNum(params.value as number)}
                </span>
            ),
        },
        {
            field: 'allotted_cif',
            headerName: 'Allotted CIF',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {fmtNum(params.value as number)}
                </span>
            ),
        },
        {
            field: 'balance_qty',
            headerName: 'Balance Qty',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => (
                <span className={params.row.id === '__TOTALS_ROW__' ? 'font-semibold' : ''}>
                    {fmtNum(params.value as number)}
                </span>
            ),
        },
        {
            field: 'effective_balance_cif',
            headerName: 'Balance CIF',
            width: 120,
            align: 'right',
            headerAlign: 'right',
            sortable: true,
            renderCell: (params) => {
                const row = params.row as unknown as LicenseOverviewItemRow & { id: string | number };
                const isTotalsRow = String(params.row.id) === '__TOTALS_ROW__';
                return (
                    <span
                        className={isTotalsRow ? 'font-semibold' : ''}
                        title={
                            !isTotalsRow && String(row.balance_cif_source) === 'LICENSE'
                                ? 'Licence-level CIF'
                                : 'Individual item CIF'
                        }
                    >
                        {fmtNum(params.value as number)}
                    </span>
                );
            },
        },
    ], []);

    if (!isActive) return null;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading items…
            </div>
        );
    }

    if (isError) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load items.")}</AlertDescription>
            </Alert>
        );
    }

    return (
        <Box
            sx={{
                width: '100%',
                height: 'calc(100vh - 15rem)',
                '& .MuiDataGrid-root': {
                    border: `1px solid ${theme.palette.divider}`,
                    backgroundColor: theme.palette.background.paper,
                    borderRadius: theme.shape.borderRadius,
                },
                '& .MuiDataGrid-cell': {
                    borderColor: theme.palette.divider,
                    py: 0.75,
                    px: 1.5,
                    fontSize: '0.8125rem',
                },
                '& .MuiDataGrid-columnHeader': {
                    backgroundColor:
                        theme.palette.mode === 'dark'
                            ? theme.palette.grey[900]
                            : theme.palette.grey[100],
                    borderColor: theme.palette.divider,
                    fontWeight: 600,
                    fontSize: '0.75rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                },
                '& .MuiDataGrid-row': {
                    '&:hover': {
                        backgroundColor: theme.palette.action.hover,
                    },
                    '&[data-rowindex="__TOTALS_ROW__"]': {
                        backgroundColor:
                            theme.palette.mode === 'dark'
                                ? theme.palette.grey[800]
                                : theme.palette.grey[200],
                        borderTop: `2px solid ${theme.palette.divider}`,
                    },
                },
            }}
        >
            <DataGrid
                rows={rows}
                columns={columns}
                pageSizeOptions={[25, 50, 100]}
                paginationModel={{ pageSize: rows.length > 100 ? 100 : 25, page: 0 }}
                onPaginationModelChange={() => {}}
                sortingMode="client"
                loading={isLoading}
                getRowId={(row) => row.id ?? Math.random()}
                disableRowSelectionOnClick
                density="compact"
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
    );
}
