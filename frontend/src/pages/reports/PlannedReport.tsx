import { useMemo } from "react";
import { Box, Stack, Typography, Button as MuiButton, CircularProgress, useTheme } from "@mui/material";
import { CalendarDays, FileSpreadsheet, Inbox, Loader2, Package, Tag } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import ActiveFilters, { type ActiveFilterItem } from "@/components/ActiveFilters";
import { useItemReportFilters } from "./itemReport/useItemReportFilters";
import { useItemReportData } from "./itemReport/useItemReportData";
import ItemReportFilters from "./itemReport/ItemReportFilters";
import ItemReportTotalsBar from "./itemReport/ItemReportTotalsBar";
import ItemReportTable from "./itemReport/ItemReportTable";
import { buildPlannedReportPath } from "./reportPaths";


export default function PlannedReport() {
    const {
        selectedItemNames, minBalance, minAvailQty, licenseStatus, selectedCompanies, excludeCompanies,
        isRestricted, purchaseStatus, productDescSearch, hsnCodeSearch, selectedNorms, selectedNotifications,
        notificationOptions, purchaseStatusOptions, normOptions, expiryDateFrom, expiryDateTo,
        setMinBalance, setMinAvailQty, setLicenseStatus, setIsRestricted,
        setProductDescSearch, setHsnCodeSearch, setExpiryDateFrom, setExpiryDateTo,
        handleItemNameChange, handleCompanyChange, handleExcludeCompanyChange, handlePurchaseStatusChange,
        handleNormsChange, handleNotificationsChange, handleClearFilters,
        hasActiveFilters, hasQuery, filters, debouncedFilters, isPending,
    } = useItemReportFilters();

    const {
        reportData, loading, downloading, itemNameOptions,
        editingCell, editValue, setEditValue, startEdit, cancelEdit, saveEdit, handleExport,
    } = useItemReportData({
        buildPath: buildPlannedReportPath,
        availableItemsPath: "planned-report/available-items/",
        debouncedFilters,
        exportFilename: "planned_report.xlsx",
    });

    const theme = useTheme();

    return (
        <Box sx={{ minHeight: '100vh', backgroundColor: theme.palette.background.default }}>
            <PageHeader
                pretitle="Reports"
                title="Planned Report"
                description={
                    reportData ? (
                        <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                            <CalendarDays className="size-3.5" style={{ color: theme.palette.text.secondary }} aria-hidden="true" />
                            <Typography variant="body2">{reportData.report_date}</Typography>
                            <Typography variant="body2" sx={{ color: 'text.secondary' }}>•</Typography>
                            <Package className="size-3.5" style={{ color: theme.palette.text.secondary }} aria-hidden="true" />
                            <Typography variant="body2">{reportData.total_items} items</Typography>
                        </Stack>
                    ) : undefined
                }
                actions={
                    <MuiButton
                        variant="contained"
                        size="small"
                        onClick={() => handleExport(filters)}
                        disabled={downloading || !hasQuery}
                        startIcon={downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                    >
                        <span style={{ display: 'inline' }}>{downloading ? 'Generating…' : 'Export Excel'}</span>
                    </MuiButton>
                }
            />

            <ItemReportFilters
                isPending={isPending}
                hasActiveFilters={hasActiveFilters}
                onClearFilters={handleClearFilters}
                minBalance={minBalance}
                onMinBalanceChange={setMinBalance}
                minAvailQty={minAvailQty}
                onMinAvailQtyChange={setMinAvailQty}
                licenseStatus={licenseStatus}
                onLicenseStatusChange={setLicenseStatus}
                expiryDateFrom={expiryDateFrom}
                onExpiryDateFromChange={setExpiryDateFrom}
                expiryDateTo={expiryDateTo}
                onExpiryDateToChange={setExpiryDateTo}
                selectedCompanies={selectedCompanies}
                onCompanyChange={handleCompanyChange}
                excludeCompanies={excludeCompanies}
                onExcludeCompanyChange={handleExcludeCompanyChange}
                isRestricted={isRestricted}
                onIsRestrictedChange={setIsRestricted}
                purchaseStatusOptions={purchaseStatusOptions}
                purchaseStatus={purchaseStatus}
                onPurchaseStatusChange={handlePurchaseStatusChange}
                normOptions={normOptions}
                selectedNorms={selectedNorms}
                onNormsChange={handleNormsChange}
                notificationOptions={notificationOptions}
                selectedNotifications={selectedNotifications}
                onNotificationsChange={handleNotificationsChange}
                productDescSearch={productDescSearch}
                onProductDescSearchChange={setProductDescSearch}
                hsnCodeSearch={hsnCodeSearch}
                onHsnCodeSearchChange={setHsnCodeSearch}
                itemNameOptions={itemNameOptions}
                selectedItemNames={selectedItemNames}
                onItemNameChange={handleItemNameChange}
            />

            {/* Active Filters Display */}
            <PlannedReportActiveFiltersDisplay
                filters={{
                    selectedItemNames,
                    minBalance,
                    minAvailQty,
                    licenseStatus,
                    selectedCompanies,
                    excludeCompanies,
                    isRestricted,
                    purchaseStatus,
                    productDescSearch,
                    hsnCodeSearch,
                    selectedNorms,
                    selectedNotifications,
                    expiryDateFrom,
                    expiryDateTo,
                }}
                onRemoveFilter={(key) => {
                    switch (key) {
                        case 'selectedItemNames': handleItemNameChange(null); break;
                        case 'minBalance': setMinBalance(200); break;
                        case 'minAvailQty': setMinAvailQty(0); break;
                        case 'licenseStatus': setLicenseStatus('active'); break;
                        case 'selectedCompanies': handleCompanyChange(null); break;
                        case 'excludeCompanies': handleExcludeCompanyChange(null); break;
                        case 'isRestricted': setIsRestricted('all'); break;
                        case 'purchaseStatus': handlePurchaseStatusChange(purchaseStatusOptions.map(o => o.value)); break;
                        case 'productDescSearch': setProductDescSearch(''); break;
                        case 'hsnCodeSearch': setHsnCodeSearch(''); break;
                        case 'selectedNorms': handleNormsChange(null); break;
                        case 'selectedNotifications': handleNotificationsChange(null); break;
                        case 'expiryDateFrom': setExpiryDateFrom(''); break;
                        case 'expiryDateTo': setExpiryDateTo(''); break;
                    }
                }}
                onClearAll={handleClearFilters}
                purchaseStatusOptions={purchaseStatusOptions}
            />

            {/* Sticky Totals Bar */}
            {!loading && hasQuery && reportData && reportData.items.length > 0 && (
                <ItemReportTotalsBar items={reportData.items} />
            )}

            {/* Report Table */}
            <Box sx={{ maxWidth: '100%' }}>
                {loading && (
                    <Box
                        sx={{
                            border: `1px solid ${theme.palette.divider}`,
                            borderRadius: 1,
                            p: 6,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            textAlign: 'center',
                        }}
                    >
                        <CircularProgress sx={{ mb: 2 }} />
                        <Typography variant="body1" sx={{ mb: 1, color: 'text.secondary' }}>
                            Loading Planned Report…
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                            Please wait while we fetch the data
                        </Typography>
                    </Box>
                )}

                {!loading && !hasQuery && (
                    <Box
                        sx={{
                            border: `1px solid ${theme.palette.divider}`,
                            borderRadius: 1,
                            p: 3,
                            textAlign: 'center',
                        }}
                    >
                        <Tag className="size-4 mx-auto" aria-hidden="true" />
                        <Typography variant="body1" sx={{ mt: 2, mb: 1, color: 'primary.main', fontWeight: 600 }}>
                            Select Filters to View Report
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                            Please select item names, search by product description, or search by HSN code to load the report data
                        </Typography>
                    </Box>
                )}

                {!loading && hasQuery && reportData && reportData.items.length === 0 && (
                    <Box
                        sx={{
                            border: `1px solid ${theme.palette.divider}`,
                            borderRadius: 1,
                            p: 3,
                            textAlign: 'center',
                        }}
                    >
                        <Inbox className="size-4 mx-auto" aria-hidden="true" />
                        <Typography variant="body1" sx={{ mt: 2, mb: 1, color: 'text.secondary' }}>
                            No items found
                        </Typography>
                        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
                            Try adjusting your filters to see more results.
                        </Typography>
                        <Box sx={{ mx: 'auto', maxWidth: 600, textAlign: 'left' }}>
                            <Typography variant="body2" sx={{ mb: 1, color: 'text.secondary' }}>
                                <strong>Tip:</strong> When searching by Product Description or HSN Code, consider:
                            </Typography>
                            <Box component="ul" sx={{ color: 'text.secondary', fontSize: '0.875rem', pl: 2 }}>
                                <li>Setting License Status to "All"</li>
                                <li>Lowering the Min Balance (CIF) to 100</li>
                                <li>Checking if your search term matches exactly (case-insensitive partial match)</li>
                            </Box>
                        </Box>
                    </Box>
                )}

                {!loading && hasQuery && reportData && reportData.items.length > 0 && (
                    <ItemReportTable
                        items={reportData.items}
                        itemNameMode="readonly"
                        editingCell={editingCell}
                        editValue={editValue}
                        onEditValueChange={setEditValue}
                        onStartEdit={startEdit}
                        onCancelEdit={cancelEdit}
                        onSaveEdit={saveEdit}
                    />
                )}
            </Box>
        </Box>
    );
}

/**
 * PlannedReportActiveFiltersDisplay — shows all active filters with individual remove buttons
 */
function PlannedReportActiveFiltersDisplay({
    filters,
    onRemoveFilter,
    onClearAll,
    purchaseStatusOptions,
}: {
    filters: {
        selectedItemNames: unknown[];
        minBalance: number;
        minAvailQty: number;
        licenseStatus: string;
        selectedCompanies: unknown[];
        excludeCompanies: unknown[];
        isRestricted: string;
        purchaseStatus: string[];
        productDescSearch: string;
        hsnCodeSearch: string;
        selectedNorms: string[];
        selectedNotifications: string[];
        expiryDateFrom: string;
        expiryDateTo: string;
    };
    onRemoveFilter: (key: string) => void;
    onClearAll: () => void;
    purchaseStatusOptions: { value: string; label: string }[];
}) {
    const activeFilters: ActiveFilterItem[] = useMemo(() => {
        const items: ActiveFilterItem[] = [];

        // Item Names
        if (filters.selectedItemNames.length > 0) {
            items.push({
                key: 'selectedItemNames',
                label: 'Item Names',
                value: `${filters.selectedItemNames.length} selected`,
            });
        }

        // Min Balance
        if (filters.minBalance !== 200) {
            items.push({
                key: 'minBalance',
                label: 'Min Balance (CIF)',
                value: `₹${filters.minBalance}`,
            });
        }

        // Min Avail Qty
        if (filters.minAvailQty !== 0) {
            items.push({
                key: 'minAvailQty',
                label: 'Min Available Qty',
                value: filters.minAvailQty.toString(),
            });
        }

        // License Status
        if (filters.licenseStatus !== 'active') {
            items.push({
                key: 'licenseStatus',
                label: 'License Status',
                value: filters.licenseStatus,
            });
        }

        // Companies
        if (filters.selectedCompanies.length > 0) {
            items.push({
                key: 'selectedCompanies',
                label: 'Companies',
                value: `${filters.selectedCompanies.length} selected`,
            });
        }

        // Exclude Companies
        if (filters.excludeCompanies.length > 0) {
            items.push({
                key: 'excludeCompanies',
                label: 'Exclude Companies',
                value: `${filters.excludeCompanies.length} excluded`,
            });
        }

        // Restricted
        if (filters.isRestricted !== 'all') {
            items.push({
                key: 'isRestricted',
                label: 'Restricted Items',
                value: filters.isRestricted === 'true' ? 'Yes' : 'No',
            });
        }

        // Purchase Status
        const defaultPurchaseStatus = purchaseStatusOptions.map(o => o.value);
        const isDefaultPurchaseStatus = filters.purchaseStatus.length === defaultPurchaseStatus.length &&
            filters.purchaseStatus.every(ps => defaultPurchaseStatus.includes(ps));
        if (!isDefaultPurchaseStatus && filters.purchaseStatus.length > 0) {
            items.push({
                key: 'purchaseStatus',
                label: 'Purchase Status',
                value: `${filters.purchaseStatus.length} selected`,
            });
        }

        // Product Description Search
        if (filters.productDescSearch) {
            items.push({
                key: 'productDescSearch',
                label: 'Product Description',
                value: `"${filters.productDescSearch}"`,
            });
        }

        // HSN Code Search
        if (filters.hsnCodeSearch) {
            items.push({
                key: 'hsnCodeSearch',
                label: 'HSN Code',
                value: `"${filters.hsnCodeSearch}"`,
            });
        }

        // Norms
        if (filters.selectedNorms.length > 0) {
            items.push({
                key: 'selectedNorms',
                label: 'SION Norms',
                value: `${filters.selectedNorms.length} selected`,
            });
        }

        // Notifications
        if (filters.selectedNotifications.length > 0) {
            items.push({
                key: 'selectedNotifications',
                label: 'Notifications',
                value: `${filters.selectedNotifications.length} selected`,
            });
        }

        // Expiry Date Range
        if (filters.expiryDateFrom || filters.expiryDateTo) {
            const dateRange = [
                filters.expiryDateFrom || '—',
                filters.expiryDateTo || '—',
            ].join(' to ');
            items.push({
                key: 'expiryDateRange',
                label: 'Expiry Date Range',
                value: dateRange,
            });
        }

        return items;
    }, [filters, purchaseStatusOptions]);

    if (activeFilters.length === 0) {
        return null;
    }

    return (
        <div className="mb-4">
            <ActiveFilters
                filters={activeFilters}
                onRemove={onRemoveFilter}
                onClearAll={onClearAll}
                showCount={true}
            />
        </div>
    );
}
