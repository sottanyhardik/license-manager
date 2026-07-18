import { useId } from "react";
import Select from "react-select";
import AsyncSelectField from "../../components/AsyncSelectField";
import { Building2, CalendarCheck, CalendarRange, DollarSign, Filter, MinusCircle, ShoppingCart, SlidersHorizontal, XCircle } from "lucide-react";

type SelectOption = {
    value: string;
    label: string;
};

interface ItemPivotFiltersProps {
    minBalance: number;
    setMinBalance: (v: number) => void;
    licenseStatus: string;
    setLicenseStatus: (v: string) => void;
    purchaseStatus: string[];
    setPurchaseStatus: (v: string[]) => void;
    purchaseStatusOptions: SelectOption[];
    expiryDateFrom: string;
    setExpiryDateFrom: (v: string) => void;
    expiryDateTo: string;
    setExpiryDateTo: (v: string) => void;
    selectedCompanies: unknown[];
    handleCompanyChange: (v: unknown) => void;
    excludeCompanies: unknown[];
    handleExcludeCompanyChange: (v: unknown) => void;
    hasActiveFilters: boolean | string;
    handleClearFilters: () => void;
    isDefaultPurchaseStatus: boolean;
}

const BALANCE_OPTIONS = [
    { value: -999999, label: "All (Including Negative)" },
    { value: 0, label: "Rs. 0 or Above" },
    { value: 100, label: "Rs. 100" },
    { value: 200, label: "Rs. 200" },
    { value: 500, label: "Rs. 500" },
    { value: 1000, label: "Rs. 1,000" },
    { value: 5000, label: "Rs. 5,000" },
    { value: 10000, label: "Rs. 10,000" },
] as const;

export function normalizeMinBalance(value: unknown, fallback = 200): number {
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
}

/** Item Pivot report filter card — extracted verbatim from ItemPivotReport. */
export default function ItemPivotFilters({
    minBalance, setMinBalance, licenseStatus, setLicenseStatus,
    purchaseStatus, setPurchaseStatus, purchaseStatusOptions,
    expiryDateFrom, setExpiryDateFrom, expiryDateTo, setExpiryDateTo,
    selectedCompanies, handleCompanyChange, excludeCompanies, handleExcludeCompanyChange,
    hasActiveFilters, handleClearFilters, isDefaultPurchaseStatus,
}: ItemPivotFiltersProps) {
    const minBalanceId = useId();
    const licenseStatusId = useId();
    const purchaseStatusId = useId();
    const expiryDateFromId = useId();
    const expiryDateToId = useId();
    const menuPortalTarget = typeof document !== "undefined" ? document.body : undefined;
    const activeFiltersVisible = Boolean(hasActiveFilters);

    return (
        <div className="mb-4 max-w-[1400px] overflow-hidden rounded-xl border border-border bg-card shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-4 py-3.5">
                <h5 className="mb-0 flex items-center gap-2 text-[15px] font-semibold">
                    <SlidersHorizontal className="size-4" aria-hidden="true" />
                    Filters
                </h5>
                {activeFiltersVisible && (
                    <button
                        type="button"
                        className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted"
                        onClick={handleClearFilters}
                    >
                        <XCircle className="size-4" aria-hidden="true" />
                        Clear Filters
                    </button>
                )}
            </div>
            <div style={{ padding: "14px 16px" }}>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                        <label className="form-label mb-2 flex items-center gap-2 font-bold" htmlFor={minBalanceId}>
                            <DollarSign className="size-4" aria-hidden="true" />
                            Minimum Balance (CIF)
                        </label>
                        <select
                            id={minBalanceId}
                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                            value={minBalance}
                            onChange={(e) => setMinBalance(normalizeMinBalance(e.target.value, minBalance))}
                        >
                            {BALANCE_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="form-label mb-2 flex items-center gap-2 font-bold" htmlFor={licenseStatusId}>
                            <CalendarCheck className="size-4" aria-hidden="true" />
                            License Status
                        </label>
                        <select
                            id={licenseStatusId}
                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                            value={licenseStatus}
                            onChange={(e) => setLicenseStatus(e.target.value)}
                        >
                            <option value="active">Active (&gt; 1 month)</option>
                            <option value="expiring_soon">Expiring Soon (30 days or less)</option>
                            <option value="expired">Expired</option>
                            <option value="all">All</option>
                        </select>
                    </div>

                    <div>
                        <label className="form-label mb-2 flex items-center gap-2 font-bold" htmlFor={purchaseStatusId}>
                            <ShoppingCart className="size-4" aria-hidden="true" />
                            Purchase Status
                        </label>
                        <Select
                            inputId={purchaseStatusId}
                            isMulti
                            options={purchaseStatusOptions}
                            value={purchaseStatusOptions.filter((option) => purchaseStatus.includes(option.value))}
                            onChange={(selected) => setPurchaseStatus(selected ? selected.map((option) => option.value) : [])}
                            placeholder="Select purchase status..."
                            classNamePrefix="select"
                            menuPortalTarget={menuPortalTarget}
                            menuPosition="fixed"
                            styles={{
                                menuPortal: (base) => ({ ...base, zIndex: 9999 }),
                                control: (base) => ({ ...base, minHeight: "38px" }),
                            }}
                        />
                    </div>

                    <div>
                        <label className="form-label mb-2 flex items-center gap-2 font-bold" htmlFor={expiryDateFromId}>
                            <CalendarRange className="size-4" aria-hidden="true" />
                            Expiry Date From
                        </label>
                        <input
                            id={expiryDateFromId}
                            type="date"
                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                            value={expiryDateFrom}
                            onChange={(e) => setExpiryDateFrom(e.target.value)}
                        />
                    </div>

                    <div>
                        <label className="form-label mb-2 flex items-center gap-2 font-bold" htmlFor={expiryDateToId}>
                            <CalendarRange className="size-4" aria-hidden="true" />
                            Expiry Date To
                        </label>
                        <input
                            id={expiryDateToId}
                            type="date"
                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                            value={expiryDateTo}
                            onChange={(e) => setExpiryDateTo(e.target.value)}
                        />
                    </div>

                    <div>
                        <div className="form-label mb-2 flex items-center gap-2 font-bold">
                            <Building2 className="size-4" aria-hidden="true" />
                            Include Companies
                        </div>
                        <div style={{ minHeight: "38px" }}>
                            <AsyncSelectField
                                endpoint="masters/companies/"
                                labelField="name"
                                valueField="id"
                                value={selectedCompanies}
                                onChange={handleCompanyChange}
                                isMulti={true}
                                placeholder="All companies..."
                                loadOnMount={false}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="form-label mb-2 flex items-center gap-2 font-bold">
                            <MinusCircle className="size-4" aria-hidden="true" />
                            Exclude Companies
                        </div>
                        <div style={{ minHeight: "38px" }}>
                            <AsyncSelectField
                                endpoint="masters/companies/"
                                labelField="name"
                                valueField="id"
                                value={excludeCompanies}
                                onChange={handleExcludeCompanyChange}
                                isMulti={true}
                                placeholder="None excluded..."
                                loadOnMount={false}
                            />
                        </div>
                    </div>
                </div>

                {activeFiltersVisible && (
                    <div className="mt-3">
                        <div className="alert alert-info mb-0 flex items-center justify-between py-2">
                            <div>
                                <Filter className="size-4" aria-hidden="true" />
                                <strong>Active Filters:</strong>
                                {!isDefaultPurchaseStatus && (
                                    <span className="chip chip-primary ml-2">
                                        Purchase: {purchaseStatus.length > 0 ? purchaseStatus.join(", ") : "none"}
                                    </span>
                                )}
                                {minBalance !== 200 && <span className="chip chip-primary ml-2">Min Balance: Rs.{minBalance}</span>}
                                {licenseStatus !== "active" && (
                                    <span className="badge bg-primary ml-2">Status: {licenseStatus.replace("_", " ")}</span>
                                )}
                                {expiryDateFrom && <span className="chip chip-primary ml-2">Expiry From: {expiryDateFrom}</span>}
                                {expiryDateTo && <span className="chip chip-primary ml-2">Expiry To: {expiryDateTo}</span>}
                                {selectedCompanies.length > 0 && (
                                    <span className="badge bg-primary ml-2">Incl. Companies: {selectedCompanies.length}</span>
                                )}
                                {excludeCompanies.length > 0 && (
                                    <span className="chip chip-primary ml-2">Excl. Companies: {excludeCompanies.length}</span>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
