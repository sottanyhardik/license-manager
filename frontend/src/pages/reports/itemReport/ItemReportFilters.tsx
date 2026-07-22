import { useId } from "react";
import Select from "react-select";
import AsyncSelectField from "@/components/AsyncSelectField";
import { Button } from "@/components/ui/button";
import {
    Bell, Building2, CalendarCheck, CalendarRange, DollarSign, FileText, Filter,
    MinusCircle, Package, ScanBarcode, ShieldCheck, ShoppingCart, SlidersHorizontal,
    Tag, Tags, XCircle,
} from "lucide-react";
import { normalizeReportNumber } from "./reportQueryString";
import type { SelectOption } from "./useItemReportFilters";

const PURCHASE_STATUS_OPTIONS: SelectOption[] = [
    {value: 'GE', label: 'GE Purchase'},
    {value: 'GO', label: 'GE Operating'},
    {value: 'SM', label: 'SM Purchase'},
    {value: 'MI', label: 'Conversion'},
    {value: 'IP', label: 'IP'},
    {value: 'CO', label: 'CO'},
];

const NORM_OPTIONS: SelectOption[] = [
    {value: 'E1', label: 'E1'},
    {value: 'E5', label: 'E5'},
    {value: 'E126', label: 'E126'},
    {value: 'E132', label: 'E132'},
];

export interface ItemReportFiltersProps {
    isPending: boolean;
    hasActiveFilters: boolean;
    onClearFilters: () => void;

    minBalance: number;
    onMinBalanceChange: (value: number) => void;
    minAvailQty: number;
    onMinAvailQtyChange: (value: number) => void;
    licenseStatus: string;
    onLicenseStatusChange: (value: string) => void;
    expiryDateFrom: string;
    onExpiryDateFromChange: (value: string) => void;
    expiryDateTo: string;
    onExpiryDateToChange: (value: string) => void;

    selectedCompanies: unknown[];
    onCompanyChange: (values: unknown[] | null) => void;
    excludeCompanies: unknown[];
    onExcludeCompanyChange: (values: unknown[] | null) => void;

    isRestricted: string;
    onIsRestrictedChange: (value: string) => void;

    purchaseStatus: string[];
    onPurchaseStatusChange: (values: string[] | null) => void;

    selectedNorms: string[];
    onNormsChange: (values: string[] | null) => void;

    notificationOptions: SelectOption[];
    selectedNotifications: string[];
    onNotificationsChange: (values: string[] | null) => void;

    productDescSearch: string;
    onProductDescSearchChange: (value: string) => void;
    hsnCodeSearch: string;
    onHsnCodeSearchChange: (value: string) => void;

    itemNameOptions: SelectOption[];
    selectedItemNames: unknown[];
    onItemNameChange: (values: unknown[] | null) => void;
}

/** Item Report / Planned Report shared filter panel — presentational, no internal state. */
export default function ItemReportFilters({
    isPending, hasActiveFilters, onClearFilters,
    minBalance, onMinBalanceChange, minAvailQty, onMinAvailQtyChange,
    licenseStatus, onLicenseStatusChange,
    expiryDateFrom, onExpiryDateFromChange, expiryDateTo, onExpiryDateToChange,
    selectedCompanies, onCompanyChange, excludeCompanies, onExcludeCompanyChange,
    isRestricted, onIsRestrictedChange,
    purchaseStatus, onPurchaseStatusChange,
    selectedNorms, onNormsChange,
    notificationOptions, selectedNotifications, onNotificationsChange,
    productDescSearch, onProductDescSearchChange, hsnCodeSearch, onHsnCodeSearchChange,
    itemNameOptions, selectedItemNames, onItemNameChange,
}: ItemReportFiltersProps) {
    const minBalanceId = useId();
    const minAvailQtyId = useId();
    const licenseStatusId = useId();
    const expiryDateFromId = useId();
    const expiryDateToId = useId();
    const purchaseStatusId = useId();
    const normsId = useId();
    const notificationId = useId();
    const restrictedId = useId();
    const productDescriptionId = useId();
    const hsnCodeId = useId();
    const itemNameFilterId = useId();

    return (
        <div className="row mb-3">
            <div className="col-span-full">
                <div className="surface-card">
                    <div className="flex items-center justify-between border-b border-border px-4 py-3.5">
                        <h5 className="mb-0 flex items-center gap-1.5 text-[15px] font-semibold">
                            <SlidersHorizontal className="size-4" aria-hidden="true" />
                            Filters
                            {isPending && (
                                <span className="ml-2 flex items-center gap-1 text-[13.5px] text-muted-foreground">
                                    <span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                    Updating...
                                </span>
                            )}
                        </h5>
                        {hasActiveFilters && (
                            <Button variant="outline" size="sm" onClick={onClearFilters}>
                                <XCircle className="size-3.5" />
                                Clear Filters
                            </Button>
                        )}
                    </div>
                    <div style={{ padding: '14px 16px' }}>
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={minBalanceId}>
                                    <DollarSign className="size-4" aria-hidden="true" />
                                    Min Balance (CIF)
                                </label>
                                <select
                                    id={minBalanceId}
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={minBalance}
                                    onChange={(e) => onMinBalanceChange(normalizeReportNumber(e.target.value, minBalance))}
                                >
                                    <option value="100">₹ 100</option>
                                    <option value="200">₹ 200</option>
                                    <option value="500">₹ 500</option>
                                    <option value="1000">₹ 1,000</option>
                                    <option value="5000">₹ 5,000</option>
                                    <option value="10000">₹ 10,000</option>
                                </select>
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={minAvailQtyId}>
                                    <Package className="size-4" aria-hidden="true" />
                                    Min Avail Qty
                                </label>
                                <select
                                    id={minAvailQtyId}
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={minAvailQty}
                                    onChange={(e) => onMinAvailQtyChange(normalizeReportNumber(e.target.value, minAvailQty))}
                                >
                                    <option value="0">0</option>
                                    <option value="100">100</option>
                                    <option value="500">500</option>
                                    <option value="1000">1,000</option>
                                    <option value="5000">5,000</option>
                                    <option value="10000">10,000</option>
                                </select>
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={licenseStatusId}>
                                    <CalendarCheck className="size-4" aria-hidden="true" />
                                    License Status
                                </label>
                                <select
                                    id={licenseStatusId}
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={licenseStatus}
                                    onChange={(e) => onLicenseStatusChange(e.target.value)}
                                >
                                    <option value="active">Active</option>
                                    <option value="expiring_soon">Expiring Soon</option>
                                    <option value="expired">Expired</option>
                                    <option value="all">All</option>
                                </select>
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={expiryDateFromId}>
                                    <CalendarRange className="size-4" aria-hidden="true" />
                                    Expiry Date From
                                </label>
                                <input
                                    id={expiryDateFromId}
                                    type="date"
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={expiryDateFrom}
                                    onChange={(e) => onExpiryDateFromChange(e.target.value)}
                                />
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={expiryDateToId}>
                                    <CalendarRange className="size-4" aria-hidden="true" />
                                    Expiry Date To
                                </label>
                                <input
                                    id={expiryDateToId}
                                    type="date"
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={expiryDateTo}
                                    onChange={(e) => onExpiryDateToChange(e.target.value)}
                                />
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2">
                                    <Building2 className="size-4" aria-hidden="true" />
                                    Include Companies
                                </label>
                                <div style={{minHeight: '38px'}}>
                                    <AsyncSelectField
                                        endpoint="masters/companies/"
                                        labelField="name"
                                        valueField="id"
                                        value={selectedCompanies}
                                        onChange={onCompanyChange}
                                        isMulti={true}
                                        placeholder="All companies..."
                                        loadOnMount={false}
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2">
                                    <MinusCircle className="size-4" aria-hidden="true" />
                                    Exclude Companies
                                </label>
                                <div style={{minHeight: '38px'}}>
                                    <AsyncSelectField
                                        endpoint="masters/companies/"
                                        labelField="name"
                                        valueField="id"
                                        value={excludeCompanies}
                                        onChange={onExcludeCompanyChange}
                                        isMulti={true}
                                        placeholder="None excluded..."
                                        loadOnMount={false}
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={restrictedId}>
                                    <ShieldCheck className="size-4" aria-hidden="true" />
                                    Is Restricted
                                </label>
                                <select
                                    id={restrictedId}
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    value={isRestricted}
                                    onChange={(e) => onIsRestrictedChange(e.target.value)}
                                >
                                    <option value="all">All</option>
                                    <option value="true">Restricted</option>
                                    <option value="false">Not Restricted</option>
                                </select>
                            </div>

                            <div className="sm:col-span-2">
                                <label className="form-label font-bold mb-2" htmlFor={purchaseStatusId}>
                                    <ShoppingCart className="size-4" aria-hidden="true" />
                                    Purchase Status
                                </label>
                                <Select
                                    inputId={purchaseStatusId}
                                    isMulti
                                    value={PURCHASE_STATUS_OPTIONS.filter(opt => purchaseStatus.includes(opt.value))}
                                    onChange={(selected) => onPurchaseStatusChange(selected ? selected.map(s => s.value) : [])}
                                    options={PURCHASE_STATUS_OPTIONS}
                                    placeholder="Select purchase status..."
                                    className="basic-multi-select"
                                    classNamePrefix="select"
                                />
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={normsId}>
                                    <Tags className="size-4" aria-hidden="true" />
                                    Norms
                                </label>
                                <Select
                                    inputId={normsId}
                                    isMulti
                                    value={NORM_OPTIONS.filter(opt => selectedNorms.includes(opt.value))}
                                    onChange={(selected) => onNormsChange(selected ? selected.map(s => s.value) : [])}
                                    options={NORM_OPTIONS}
                                    placeholder="Select norms..."
                                    className="basic-multi-select"
                                    classNamePrefix="select"
                                />
                            </div>

                            <div>
                                <label className="form-label font-bold mb-2" htmlFor={notificationId}>
                                    <Bell className="size-4" aria-hidden="true" />
                                    Notification
                                </label>
                                <Select
                                    inputId={notificationId}
                                    isMulti
                                    value={notificationOptions.filter(opt => selectedNotifications.includes(opt.value))}
                                    onChange={(selected) => onNotificationsChange(selected ? selected.map(s => s.value) : [])}
                                    options={notificationOptions}
                                    placeholder="Select notification..."
                                    className="basic-multi-select"
                                    classNamePrefix="select"
                                />
                            </div>
                        </div>

                        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            <div className="sm:col-span-full">
                                <label className="form-label font-bold mb-2" htmlFor={productDescriptionId}>
                                    <FileText className="size-4" aria-hidden="true" />
                                    Product Description
                                </label>
                                <input
                                    id={productDescriptionId}
                                    type="text"
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    placeholder="Search by product description..."
                                    value={productDescSearch}
                                    onChange={(e) => onProductDescSearchChange(e.target.value)}
                                />
                            </div>
                            <div className="sm:col-span-full">
                                <label className="form-label font-bold mb-2" htmlFor={hsnCodeId}>
                                    <ScanBarcode className="size-4" aria-hidden="true" />
                                    HSN Code
                                </label>
                                <input
                                    id={hsnCodeId}
                                    type="text"
                                    className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                    placeholder="Search by HSN code..."
                                    value={hsnCodeSearch}
                                    onChange={(e) => onHsnCodeSearchChange(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            <div className="col-span-full">
                                <label className="form-label font-bold mb-2" htmlFor={itemNameFilterId}>
                                    <Tag className="size-4" aria-hidden="true" />
                                    Filter by Item Name (Multi-select)
                                </label>
                                <Select
                                    inputId={itemNameFilterId}
                                    isMulti
                                    value={itemNameOptions.filter(opt => selectedItemNames.includes(opt.value))}
                                    onChange={(selected) => onItemNameChange(selected ? selected.map(s => s.value) : [])}
                                    options={itemNameOptions}
                                    placeholder="Select item names..."
                                    className="basic-multi-select"
                                    classNamePrefix="select"
                                    // Portal the menu to <body> so it isn't clipped/hidden behind the
                                    // report card below the filter panel.
                                    menuPortalTarget={typeof document !== 'undefined' ? document.body : undefined}
                                    menuPosition="fixed"
                                    styles={{ menuPortal: (base) => ({ ...base, zIndex: 9999 }) }}
                                />
                            </div>
                        </div>

                        {hasActiveFilters && (
                            <div className="mt-3">
                                <div
                                    className="alert alert-info flex justify-between items-center py-2 mb-0">
                                    <div>
                                        <Filter className="size-4" aria-hidden="true" />
                                        <strong>Active Filters:</strong>
                                        {minBalance !== 200 && <span className="chip chip-primary ml-2">Min Balance: ₹{minBalance}</span>}
                                        {minAvailQty !== 0 && <span className="chip chip-primary ml-2">Min Qty: {minAvailQty}</span>}
                                        {licenseStatus !== 'active' && <span
                                            className="badge bg-primary ml-2">Status: {licenseStatus.replace('_', ' ')}</span>}
                                        {selectedCompanies.length > 0 && <span className="chip chip-primary ml-2">Incl. Companies: {selectedCompanies.length}</span>}
                                        {excludeCompanies.length > 0 && <span className="chip chip-primary ml-2">Excl. Companies: {excludeCompanies.length}</span>}
                                        {isRestricted !== 'all' && <span className="chip chip-primary ml-2">Is Restricted: {isRestricted === 'true' ? 'Yes' : 'No'}</span>}
                                        {purchaseStatus.length > 0 && purchaseStatus.length < 6 && <span className="chip chip-primary ml-2">Purchase Status: {purchaseStatus.length}</span>}
                                        {selectedItemNames.length > 0 && <span className="chip chip-primary ml-2">Item Names: {selectedItemNames.length}</span>}
                                        {productDescSearch !== '' && <span className="chip chip-primary ml-2">Product Desc: "{productDescSearch}"</span>}
                                        {hsnCodeSearch !== '' && <span className="chip chip-primary ml-2">HSN Code: "{hsnCodeSearch}"</span>}
                                        {selectedNorms.length > 0 && <span className="chip chip-primary ml-2">Norms: {selectedNorms.length}</span>}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
