import { useEffect, useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import api from "../../api/axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { CalendarDays, FileSpreadsheet, Inbox, Loader2, Package, Tag } from "lucide-react";
import { usePagination } from "@/hooks/usePagination";
import DataPagination from "@/components/DataPagination";
import PageHeader from "@/components/PageHeader";
import ActiveFilters, { type ActiveFilterItem } from "@/components/ActiveFilters";
import { useItemReportFilters } from "./itemReport/useItemReportFilters";
import { useItemReportData } from "./itemReport/useItemReportData";
import ItemReportFilters from "./itemReport/ItemReportFilters";
import ItemReportTotalsBar from "./itemReport/ItemReportTotalsBar";
import ItemReportTable from "./itemReport/ItemReportTable";
import { buildItemReportPath } from "./reportPaths";



export default function ItemReport() {
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
        reportData, setReportData, loading, downloading, itemNameOptions,
        editingCell, editValue, setEditValue, startEdit, cancelEdit, saveEdit, handleExport,
    } = useItemReportData({
        buildPath: buildItemReportPath,
        availableItemsPath: "item-report/available-items/",
        debouncedFilters,
        exportFilename: "item_report.xlsx",
    });

    // Paginate by LICENSE GROUP (not raw item row) — a license's item rows
    // must never be split across a page boundary, since the first row of
    // each group carries the license-level columns the rest rowSpan into.
    // The report's own data is already sorted by expiry date server-side
    // (see item_report.py's generate_report), so grouping here preserves
    // that order. Totals bar / Excel export always use the FULL,
    // unpaginated `reportData.items` — only the on-screen table paginates.
    const licenseGroups = useMemo(() => {
        if (!reportData?.items) return [];
        const map = new Map<string, any[]>();
        reportData.items.forEach((item: any) => {
            if (!map.has(item.license_id)) map.set(item.license_id, []);
            map.get(item.license_id)!.push(item);
        });
        return Array.from(map.values());
    }, [reportData]);

    const pagination = usePagination({ initialPageSize: 25 });
    useEffect(() => {
        pagination.setTotalItems(licenseGroups.length);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [licenseGroups.length]);
    useEffect(() => {
        // Reset to page 1 whenever the filtered dataset changes, so the
        // user never gets stranded on a page beyond the new result set.
        pagination.goToPage(1);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [reportData]);

    const groupStart = (pagination.currentPage - 1) * pagination.pageSize;
    const priorPageGroups = useMemo(
        () => licenseGroups.slice(0, groupStart),
        [licenseGroups, groupStart]
    );
    // Sr No increments once per raw item row (see ItemReportTable), so the
    // continuation offset for page N+1 must be the raw-row count of every
    // license group on prior pages — not the group count itself.
    const startSrNo = useMemo(
        () => priorPageGroups.reduce((sum, group) => sum + group.length, 0),
        [priorPageGroups]
    );
    const pageItems = useMemo(
        () => licenseGroups.slice(groupStart, groupStart + pagination.pageSize).flat(),
        [licenseGroups, groupStart, pagination.pageSize]
    );

    const handleItemNamesEdit = async (item: any, selectedOptions: { value: unknown; label: string }[] | null) => {
        try {
            const itemNameIds = selectedOptions ? selectedOptions.map(v => v.value) : [];
            await api.patch(`license-items/${item.id}/`, {
                items: itemNameIds
            });
            toast.success('Item names updated successfully');

            // Fetch updated item data to check if it still matches filters
            const response = await api.get(buildItemReportPath({format: "json", ...filters}));
            const updatedReportData = response.data;

            // Find the updated item in the new data
            const updatedItem = updatedReportData.items.find((i: any) => i.id === item.id);

            if (updatedItem) {
                // Item still matches filters - update the row
                setReportData((prev) => {
                    if (!prev) return prev;
                    const updatedItems = prev.items.map((i: any) => i.id === item.id ? updatedItem : i);
                    return {...prev, items: updatedItems};
                });
            } else {
                // Item no longer matches filters - remove it from the list
                setReportData((prev) => {
                    if (!prev) return prev;
                    const filteredItems = prev.items.filter((i: any) => i.id !== item.id);
                    return {...prev, items: filteredItems, total_items: filteredItems.length};
                });
                toast.info('Item removed from list as it no longer matches the filters');
            }
        } catch {
            toast.error('Failed to update item names. Please try again.');
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <PageHeader
                pretitle="Reports"
                title="Item Report"
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
                        variant="default"
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
            <ItemReportActiveFiltersDisplay
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
            <div className="row mt-3">
                <div className="col-span-full">
                    {loading && (
                        <Card>
                            <CardContent className="flex flex-col items-center py-8 text-center">
                                <Loader2 className="mb-2 size-8 animate-spin text-primary" />
                                <h5 className="text-muted-foreground">Loading Item Report…</h5>
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
                                <div className="mx-auto mt-3 max-w-[600px] text-left">
                                    <p className="mb-2 text-sm text-muted-foreground"><strong>Tip:</strong> When searching by Product Description or HSN Code, consider:</p>
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
                        <>
                            <ItemReportTable
                                items={pageItems}
                                totalsItems={reportData.items}
                                startSrNo={startSrNo}
                                itemNameMode="editable"
                                itemNameOptions={itemNameOptions}
                                onItemNamesChange={handleItemNamesEdit}
                                editingCell={editingCell}
                                editValue={editValue}
                                onEditValueChange={setEditValue}
                                onStartEdit={startEdit}
                                onCancelEdit={cancelEdit}
                                onSaveEdit={saveEdit}
                            />
                            <DataPagination
                                currentPage={pagination.currentPage}
                                totalPages={pagination.totalPages}
                                pageSize={pagination.pageSize}
                                hasNext={!pagination.isLastPage}
                                hasPrevious={!pagination.isFirstPage}
                                totalItems={licenseGroups.length}
                                onPageChange={pagination.goToPage}
                                onPageSizeChange={pagination.setPageSize}
                            />
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

/**
 * ItemReportActiveFiltersDisplay — shows all active filters with individual remove buttons
 */
function ItemReportActiveFiltersDisplay({
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
