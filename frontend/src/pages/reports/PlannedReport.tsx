import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import PageHeader from "@/components/PageHeader";
import { CalendarDays, FileSpreadsheet, Inbox, Loader2, Package, Tag } from "lucide-react";
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

    return (
        <div className="min-h-screen bg-background">
            <PageHeader
                pretitle="Reports"
                title="Planned Report"
                description={
                    reportData ? (
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                            <CalendarDays className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span>{reportData.report_date}</span>
                            <span className="text-muted-foreground">•</span>
                            <Package className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                            <span>{reportData.total_items} items</span>
                        </div>
                    ) : undefined
                }
                actions={
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleExport(filters)}
                        disabled={downloading || !hasQuery}
                    >
                        {downloading ? <Loader2 className="size-3.5 animate-spin shrink-0" /> : <FileSpreadsheet className="size-3.5 shrink-0" />}
                        <span className="hidden sm:inline">{downloading ? 'Generating…' : 'Export Excel'}</span>
                        <span className="sm:hidden">{downloading ? '…' : 'Export'}</span>
                    </Button>
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
            <div className="max-w-full">
                {loading && (
                    <Card>
                        <CardContent className="flex flex-col items-center py-12 text-center">
                            <Loader2 className="mb-3 size-10 animate-spin text-primary" />
                            <h5 className="text-muted-foreground">Loading Planned Report…</h5>
                            <p className="text-muted-foreground text-sm">Please wait while we fetch the data</p>
                        </CardContent>
                    </Card>
                )}

                {!loading && !hasQuery && (
                    <Card>
                        <CardContent className="py-5 text-center">
                            <Tag className="size-4" aria-hidden="true" />
                            <h5 className="mt-3 text-primary">Select Filters to View Report</h5>
                            <p className="text-muted-foreground">Please select item names, search by product description, or search by HSN code to load the report data</p>
                        </CardContent>
                    </Card>
                )}

                {!loading && hasQuery && reportData && reportData.items.length === 0 && (
                    <Card>
                        <CardContent className="py-5 text-center">
                            <Inbox className="size-4" aria-hidden="true" />
                            <h5 className="mt-3 text-muted-foreground">No items found</h5>
                            <p className="text-muted-foreground">Try adjusting your filters to see more results.</p>
                            <div className="mt-3 text-left" style={{maxWidth: '600px', margin: '0 auto'}}>
                                <p className="text-sm text-muted-foreground mb-2"><strong>Tip:</strong> When searching by Product Description or HSN Code, consider:</p>
                                <ul className="text-sm text-muted-foreground">
                                    <li>Setting License Status to "All"</li>
                                    <li>Lowering the Min Balance (CIF) to 100</li>
                                    <li>Checking if your search term matches exactly (case-insensitive partial match)</li>
                                </ul>
                            </div>
                        </CardContent>
                    </Card>
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
            </div>
        </div>
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
