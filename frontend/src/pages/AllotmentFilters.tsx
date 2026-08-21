import Select from "react-select";
import { useRef } from "react";
import HybridSelect from "../components/HybridSelect";
import DateRangeFilter from "../components/DateRangeFilter";
import { Filter, XCircle } from "lucide-react";

interface AllotmentFiltersProps {
    filters: Record<string, string | null>;
    setFilters: (f: any) => void;
    availableItemNames: { value: any; label: string }[];
    notificationOptions: { value: string; display_name: string }[];
    purchaseStatusOptions: { value: string; label: string }[];
    routePlanningTarget?: { id: number; name: string; sion?: string | null } | null;
    defaultSearchMode?: "PLAN" | "ACTUAL";
    defaultItemId?: number | null;
}

/** Allotment-action filter card — extracted verbatim from AllotmentAction. */
export default function AllotmentFilters({ filters, setFilters, availableItemNames, notificationOptions, purchaseStatusOptions, routePlanningTarget, defaultSearchMode = "ACTUAL", defaultItemId = null }: AllotmentFiltersProps) {
    const isPlanMode = filters.debit_based_on === "PLAN";
    // Keep only the value that this control wrote itself.  A user edit clears
    // this marker, so clearing the target never destroys independent text.
    const autoCopiedDescription = useRef<string | null>(null);

    const setPlanningTarget = (selected: { value: unknown; label: string } | null) => {
        const itemId = selected ? String(selected.value) : "";
        if (!isPlanMode) {
            setFilters({ ...filters, item_id: itemId });
            return;
        }

        const nextDescription = selected
            ? selected.label
            : filters.description === autoCopiedDescription.current
                ? ""
                : filters.description;
        autoCopiedDescription.current = selected ? selected.label : null;
        setFilters({ ...filters, item_id: itemId, description: nextDescription });
    };
    return (
                    <div className="mb-3 overflow-hidden rounded-lg border border-border/60 bg-muted/40">
                        <div className="flex items-center justify-between border-b border-border/50 px-3 py-2">
                            <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.08em] text-muted-foreground">
                                <Filter className="size-4" aria-hidden="true" /> Filters
                            </span>
                            <button
                                className="cursor-pointer border-0 bg-transparent p-0 text-xs text-muted-foreground no-underline underline-offset-2 hover:underline"
                                onClick={() => setFilters({
                                    description: "",
                                    exporter: "",
                                    exclude_exporter: "",
                                    license_number: "",
                                    available_quantity_gte: "50",
                                    available_quantity_lte: "",
                                    available_value_gte: "100",
                                    available_value_lte: "",
                                    notification_number: "",
                                    norm_class: "",
                                    hs_code: "",
                                    is_expired: "all",
                                    is_restricted: "all",
                                    purchase_status: purchaseStatusOptions.map(o => o.value).join(','),
                                    license_status: "active",
                                    item_id: defaultItemId == null ? "" : String(defaultItemId),
                                    expiry_date_from: "",
                                    expiry_date_to: "",
                                    debit_based_on: defaultSearchMode
                                })}
                            >
                                <XCircle className="size-4" aria-hidden="true" />Clear All
                            </button>
                        </div>
                        <div className="p-4">
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                                <div className="col-span-full sm:col-span-2 lg:col-span-4">
                                    <label className="form-label">{isPlanMode ? "Filter By Planning Target Item" : "Filter By Actual Item Name"}</label>
                                    <Select
                                        value={filters.item_id ? (() => {
                                            const item = availableItemNames.find(i => String(i.value) === String(filters.item_id));
                                            return item || {value: filters.item_id, label: filters.item_id};
                                        })() : null}
                                        onChange={setPlanningTarget}
                                        options={availableItemNames}
                                        placeholder={isPlanMode ? "Select a planning item" : "Select an actual item to find available licences"}
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                        isDisabled={isPlanMode && Boolean(routePlanningTarget)}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Norm Class</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/sion-classes/?is_active=true", label_field: "norm_class"}}
                                        value={filters.norm_class}
                                        onChange={(value) => setFilters({...filters, norm_class: value as string})}
                                        placeholder="All Norm Classes"
                                        isClearable={true}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Notification Number</label>
                                    <select
                                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                        value={filters.notification_number}
                                        onChange={(e) => setFilters({...filters, notification_number: e.target.value})}
                                    >
                                        <option value="">All</option>
                                        {notificationOptions.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.display_name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="form-label">License Number</label>
                                    <input
                                        type="text"
                                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                        placeholder="Filter by license number..."
                                        value={filters.license_number}
                                        onChange={(e) => setFilters({...filters, license_number: e.target.value})}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Item Description</label>
                                    <input
                                        type="text"
                                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                        placeholder="Filter by item description..."
                                        value={filters.description}
                                        onChange={(e) => {
                                            if (autoCopiedDescription.current !== null && e.target.value !== autoCopiedDescription.current) {
                                                autoCopiedDescription.current = null;
                                            }
                                            setFilters({...filters, description: e.target.value});
                                        }}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Exporter</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/companies/", label_field: "name"}}
                                        value={filters.exporter}
                                        onChange={(value) => setFilters({...filters, exporter: value as string})}
                                        placeholder="All Exporters"
                                        isClearable={true}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Exclude Exporter</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/companies/", label_field: "name"}}
                                        value={filters.exclude_exporter}
                                        onChange={(value) => setFilters({...filters, exclude_exporter: value as string})}
                                        placeholder="None"
                                        isClearable={true}
                                    />
                                </div>
                                    <div>
                                        <label className="form-label">HS Code</label>
                                        <input
                                            type="text"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.hs_code}
                                            onChange={(e) => setFilters({...filters, hs_code: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Min Available Qty</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_quantity_gte}
                                            onChange={(e) => setFilters({...filters, available_quantity_gte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Max Available Qty</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_quantity_lte}
                                            onChange={(e) => setFilters({...filters, available_quantity_lte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Min Available Value</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_value_gte}
                                            onChange={(e) => setFilters({...filters, available_value_gte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Max Available Value</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_value_lte}
                                            onChange={(e) => setFilters({...filters, available_value_lte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Is Restricted</label>
                                        <select
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.is_restricted}
                                            onChange={(e) => setFilters({...filters, is_restricted: e.target.value})}
                                        >
                                            <option value="all">All</option>
                                            <option value="true">Restricted</option>
                                            <option value="false">Not Restricted</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="form-label">Purchase Status</label>
                                        <Select
                                            isMulti
                                            value={filters.purchase_status ? filters.purchase_status.split(',').map(s => {
                                                const opt = purchaseStatusOptions.find(o => o.value === s);
                                                return opt || {value: s, label: s};
                                            }) : []}
                                            onChange={(selected) => setFilters({...filters, purchase_status: selected ? selected.map(s => s.value).join(',') : ''})}
                                            options={purchaseStatusOptions}
                                            placeholder="All"
                                            className="basic-multi-select"
                                            classNamePrefix="select"
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Debit Based On</label>
                                        <select
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.debit_based_on || "PLAN"}
                                            onChange={(e) => setFilters({...filters, debit_based_on: e.target.value, item_id: ""})}
                                        >
                                            <option value="PLAN">Plan</option>
                                            <option value="ACTUAL">Actual</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="form-label">License Status</label>
                                        <select
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.license_status}
                                            onChange={(e) => setFilters({...filters, license_status: e.target.value})}
                                        >
                                            <option value="all">All</option>
                                            <option value="active">Active</option>
                                            <option value="expired">Expired</option>
                                            <option value="expiring_soon">Expiring Soon</option>
                                        </select>
                                    </div>
                                    <div className="sm:col-span-2">
                                        <DateRangeFilter
                                            label="Expiry Date"
                                            fromValue={filters.expiry_date_from}
                                            toValue={filters.expiry_date_to}
                                            onFromChange={(v) => setFilters({...filters, expiry_date_from: v})}
                                            onToChange={(v) => setFilters({...filters, expiry_date_to: v})}
                                            onClear={() => setFilters({...filters, expiry_date_from: "", expiry_date_to: ""})}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
    );
}
