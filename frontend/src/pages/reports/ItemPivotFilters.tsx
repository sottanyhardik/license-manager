import Select from "react-select";
import AsyncSelectField from "../../components/AsyncSelectField";
import { Building2, CalendarCheck, CalendarRange, DollarSign, Filter, MinusCircle, ShoppingCart, SlidersHorizontal, XCircle } from "lucide-react";

interface ItemPivotFiltersProps {
    minBalance: number;
    setMinBalance: (v: number) => void;
    licenseStatus: string;
    setLicenseStatus: (v: string) => void;
    purchaseStatus: string[];
    setPurchaseStatus: (v: string[]) => void;
    purchaseStatusOptions: any[];
    expiryDateFrom: string;
    setExpiryDateFrom: (v: string) => void;
    expiryDateTo: string;
    setExpiryDateTo: (v: string) => void;
    selectedCompanies: any[];
    handleCompanyChange: (v: any) => void;
    excludeCompanies: any[];
    handleExcludeCompanyChange: (v: any) => void;
    hasActiveFilters: unknown;
    handleClearFilters: () => void;
    isDefaultPurchaseStatus: boolean;
}

/** Item Pivot report filter card — extracted verbatim from ItemPivotReport. */
export default function ItemPivotFilters({
    minBalance, setMinBalance, licenseStatus, setLicenseStatus,
    purchaseStatus, setPurchaseStatus, purchaseStatusOptions,
    expiryDateFrom, setExpiryDateFrom, expiryDateTo, setExpiryDateTo,
    selectedCompanies, handleCompanyChange, excludeCompanies, handleExcludeCompanyChange,
    hasActiveFilters, handleClearFilters, isDefaultPurchaseStatus,
}: ItemPivotFiltersProps) {
    return (
                <div className="mb-4 overflow-hidden rounded-xl border border-border bg-card shadow-sm" style={{maxWidth: '1400px'}}>
                            <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--tb-border)' }}
                                 className="flex justify-between items-center">
                                <h5 className="mb-0" style={{ fontWeight: 600, fontSize: 15 }}>
                                    <SlidersHorizontal className="size-4" aria-hidden="true" />
                                    Filters
                                </h5>
                                {hasActiveFilters && (
                                    <button
                                        type="button"
                                        className="flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted cursor-pointer"
                                        onClick={handleClearFilters}
                                    >
                                        <XCircle className="size-4" aria-hidden="true" />
                                        Clear Filters
                                    </button>
                                )}
                            </div>
                            <div style={{ padding: '14px 16px' }}>
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                                    <div>
                                        <label className="form-label font-bold mb-2">
                                            <DollarSign className="size-4" aria-hidden="true" />
                                            Minimum Balance (CIF)
                                        </label>
                                        <select
                                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                            value={minBalance}
                                            onChange={(e) => setMinBalance(parseInt(e.target.value))}
                                        >
                                            <option value="-999999">All (Including Negative)</option>
                                            <option value="0">₹ 0 or Above</option>
                                            <option value="100">₹ 100</option>
                                            <option value="200">₹ 200</option>
                                            <option value="500">₹ 500</option>
                                            <option value="1000">₹ 1,000</option>
                                            <option value="5000">₹ 5,000</option>
                                            <option value="10000">₹ 10,000</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="form-label font-bold mb-2">
                                            <CalendarCheck className="size-4" aria-hidden="true" />
                                            License Status
                                        </label>
                                        <select
                                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                            value={licenseStatus}
                                            onChange={(e) => setLicenseStatus(e.target.value)}
                                        >
                                            <option value="active">Active ({">"} 1 month)</option>
                                            <option value="expiring_soon">Expiring Soon (≤ 30 days)</option>
                                            <option value="expired">Expired</option>
                                            <option value="all">All</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="form-label font-bold mb-2">
                                            <ShoppingCart className="size-4" aria-hidden="true" />
                                            Purchase Status
                                        </label>
                                        <Select
                                            isMulti
                                            options={purchaseStatusOptions}
                                            value={purchaseStatusOptions.filter(o => purchaseStatus.includes(o.value))}
                                            onChange={(selected) => setPurchaseStatus(selected ? selected.map(s => s.value) : [])}
                                            placeholder="Select purchase status..."
                                            classNamePrefix="select"
                                            menuPortalTarget={document.body}
                                            menuPosition="fixed"
                                            styles={{
                                                menuPortal: (base) => ({...base, zIndex: 9999}),
                                                control: (base) => ({...base, minHeight: '38px'}),
                                            }}
                                        />
                                    </div>

                                    <div>
                                        <label className="form-label font-bold mb-2">
                                            <CalendarRange className="size-4" aria-hidden="true" />
                                            Expiry Date From
                                        </label>
                                        <input
                                            type="date"
                                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                            value={expiryDateFrom}
                                            onChange={(e) => setExpiryDateFrom(e.target.value)}
                                        />
                                    </div>

                                    <div>
                                        <label className="form-label font-bold mb-2">
                                            <CalendarRange className="size-4" aria-hidden="true" />
                                            Expiry Date To
                                        </label>
                                        <input
                                            type="date"
                                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                            value={expiryDateTo}
                                            onChange={(e) => setExpiryDateTo(e.target.value)}
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
                                                onChange={handleCompanyChange}
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
                                                onChange={handleExcludeCompanyChange}
                                                isMulti={true}
                                                placeholder="None excluded..."
                                                loadOnMount={false}
                                            />
                                        </div>
                                    </div>
                                </div>

                                {hasActiveFilters && (
                                    <div className="mt-3">
                                        <div
                                            className="alert alert-info flex justify-between items-center py-2 mb-0">
                                            <div>
                                                <Filter className="size-4" aria-hidden="true" />
                                                <strong>Active Filters:</strong>
                                                {!isDefaultPurchaseStatus && (
                                                    <span className="chip chip-primary ml-2">
                                                        Purchase: {purchaseStatus.length > 0 ? purchaseStatus.join(', ') : 'none'}
                                                    </span>
                                                )}
                                                {minBalance !== 200 && <span className="chip chip-primary ml-2">Min Balance: ₹{minBalance}</span>}
                                                {licenseStatus !== 'active' && <span
                                                    className="badge bg-primary ml-2">Status: {licenseStatus.replace('_', ' ')}</span>}
                                                {expiryDateFrom && <span className="chip chip-primary ml-2">Expiry From: {expiryDateFrom}</span>}
                                                {expiryDateTo && <span className="chip chip-primary ml-2">Expiry To: {expiryDateTo}</span>}
                                                {selectedCompanies.length > 0 && <span
                                                    className="badge bg-primary ml-2">Incl. Companies: {selectedCompanies.length}</span>}
                                                {excludeCompanies.length > 0 && <span className="chip chip-primary ml-2">Excl. Companies: {excludeCompanies.length}</span>}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
    );
}
