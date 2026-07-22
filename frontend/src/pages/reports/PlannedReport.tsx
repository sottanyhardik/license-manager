import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CalendarDays, FileSpreadsheet, Inbox, Loader2, Package, Tag } from "lucide-react";
import { reportQueryString, type ReportQueryOptions } from "./itemReport/reportQueryString";
import { useItemReportFilters } from "./itemReport/useItemReportFilters";
import { useItemReportData } from "./itemReport/useItemReportData";
import ItemReportFilters from "./itemReport/ItemReportFilters";
import ItemReportTotalsBar from "./itemReport/ItemReportTotalsBar";
import ItemReportTable from "./itemReport/ItemReportTable";

export function buildPlannedReportPath(options: ReportQueryOptions): string {
    return `reports/planned-report/?${reportQueryString(options)}`;
}

export default function PlannedReport() {
    const navigate = useNavigate();

    const {
        selectedItemNames, minBalance, minAvailQty, licenseStatus, selectedCompanies, excludeCompanies,
        isRestricted, purchaseStatus, productDescSearch, hsnCodeSearch, selectedNorms, selectedNotifications,
        notificationOptions, expiryDateFrom, expiryDateTo,
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
            {/* Tabler-style page header */}
            <div className="page-header">
                <div className="min-w-0">
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span className="mx-1.5 opacity-50">/</span>
                        Reports
                        <span className="mx-1.5 opacity-50">/</span>
                        Planned Report
                    </div>
                    <h1>Planned Report</h1>
                    {reportData && (
                        <div className="mt-1 flex items-center gap-1 text-[12.5px] text-muted-foreground">
                            <CalendarDays className="size-3.5" aria-hidden="true" />
                            {reportData.report_date}
                            <span className="mx-2 opacity-50">•</span>
                            <Package className="size-3.5" aria-hidden="true" />
                            {reportData.total_items} items
                        </div>
                    )}
                </div>
                <div className="page-actions">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleExport(filters)}
                        disabled={downloading || !hasQuery}
                    >
                        {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                        {downloading ? 'Generating…' : 'Excel'}
                    </Button>
                </div>
            </div>

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
                purchaseStatus={purchaseStatus}
                onPurchaseStatusChange={handlePurchaseStatusChange}
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

            {/* Sticky Totals Bar */}
            {!loading && hasQuery && reportData && reportData.items.length > 0 && (
                <ItemReportTotalsBar items={reportData.items} />
            )}

            {/* Report Table */}
            <div className="row">
                <div className="col-span-full">
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
        </div>
    );
}
