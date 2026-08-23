import { useMemo } from "react";
import Select from "react-select";
import HybridSelect from "../components/HybridSelect";
import DateRangeFilter from "../components/DateRangeFilter";
import { FilterGrid, FilterPanel } from "../components/filters/FilterPanel";

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

const controlClass = "flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-[13px] outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25";

export default function AllotmentFilters({ filters, setFilters, availableItemNames, notificationOptions, purchaseStatusOptions, routePlanningTarget, defaultSearchMode = "ACTUAL", defaultItemId = null }: AllotmentFiltersProps) {
    const isPlanMode = filters.debit_based_on === "PLAN";
    const defaults = useMemo(() => ({
        description: "", exporter: "", exclude_exporter: "", license_number: "", available_quantity_gte: "50", available_quantity_lte: "", available_value_gte: "100", available_value_lte: "", notification_number: "", norm_class: "", hs_code: "", is_expired: "all", is_restricted: "all", purchase_status: purchaseStatusOptions.map(o => o.value).join(','), license_status: "active", item_id: defaultItemId == null ? "" : String(defaultItemId), expiry_date_from: "", expiry_date_to: "", debit_based_on: defaultSearchMode,
    }), [defaultItemId, defaultSearchMode, purchaseStatusOptions]);
    const activeCount = Object.keys(defaults).filter(field => String(filters[field] ?? "") !== String(defaults[field] ?? "")).length;
    const itemLabel = isPlanMode ? "Filter By Planning Target Item" : "Filter By Actual Item Name";

    return <div className="mb-3"><FilterPanel activeCount={activeCount} onClear={() => setFilters(defaults)} clearDisabled={activeCount === 0}>
        <FilterGrid>
            <div className="min-w-[150px] flex-1 sm:max-w-[190px]"><label className="form-label text-[11px]">License Number</label><input className={controlClass} placeholder="Search licence…" value={filters.license_number || ""} onChange={(e) => setFilters({ ...filters, license_number: e.target.value })} /></div>
            <div className="min-w-[190px] flex-[1.25]"><label className="form-label text-[11px]">{itemLabel}</label><Select value={filters.item_id ? availableItemNames.find(i => String(i.value) === String(filters.item_id)) || { value: filters.item_id, label: filters.item_id } : null} onChange={(selected) => setFilters({ ...filters, item_id: selected ? String(selected.value) : "" })} options={availableItemNames} placeholder={isPlanMode ? "Planning item" : "Actual item"} className="basic-multi-select text-[13px]" classNamePrefix="select" isDisabled={isPlanMode && Boolean(routePlanningTarget)} /></div>
            <div className="min-w-[130px] flex-1"><label className="form-label text-[11px]">Norm Class</label><HybridSelect fieldMeta={{ endpoint: "masters/sion-classes/?is_active=true", label_field: "norm_class" }} value={filters.norm_class} onChange={(value) => setFilters({ ...filters, norm_class: value as string })} placeholder="All" isClearable /></div>
            <div className="min-w-[140px] flex-1"><label className="form-label text-[11px]">Exporter</label><HybridSelect fieldMeta={{ endpoint: "masters/companies/", label_field: "name" }} value={filters.exporter} onChange={(value) => setFilters({ ...filters, exporter: value as string })} placeholder="All" isClearable /></div>
            <div className="w-[94px]"><label className="form-label text-[11px]">Min Available Qty</label><input type="number" className={controlClass} value={filters.available_quantity_gte || ""} onChange={(e) => setFilters({ ...filters, available_quantity_gte: e.target.value })} /></div>
            <div className="w-[116px]"><label className="form-label text-[11px]">Licence Status</label><select className={controlClass} value={filters.license_status || "active"} onChange={(e) => setFilters({ ...filters, license_status: e.target.value })}><option value="all">All</option><option value="active">Active</option><option value="expired">Expired</option><option value="expiring_soon">Expiring Soon</option></select></div>
            <div className="w-[102px]"><label className="form-label text-[11px]">Debit Based On</label><select className={controlClass} value={filters.debit_based_on || "PLAN"} onChange={(e) => setFilters({ ...filters, debit_based_on: e.target.value, item_id: "" })}><option value="PLAN">Plan</option><option value="ACTUAL">Actual</option></select></div>
            <div><label className="form-label">Notification Number</label><select className={controlClass} value={filters.notification_number || ""} onChange={(e) => setFilters({ ...filters, notification_number: e.target.value })}><option value="">All</option>{notificationOptions.map(option => <option key={option.value} value={option.value}>{option.display_name}</option>)}</select></div>
            <div><label className="form-label">Item Description</label><input className={controlClass} value={filters.description || ""} onChange={(e) => setFilters({ ...filters, description: e.target.value })} /></div>
            <div><label className="form-label">Exclude Exporter</label><HybridSelect fieldMeta={{ endpoint: "masters/companies/", label_field: "name" }} value={filters.exclude_exporter} onChange={(value) => setFilters({ ...filters, exclude_exporter: value as string })} placeholder="None" isClearable /></div>
            <div><label className="form-label">HS Code</label><input className={controlClass} value={filters.hs_code || ""} onChange={(e) => setFilters({ ...filters, hs_code: e.target.value })} /></div>
            <div><label className="form-label">Max Available Qty</label><input type="number" className={controlClass} value={filters.available_quantity_lte || ""} onChange={(e) => setFilters({ ...filters, available_quantity_lte: e.target.value })} /></div>
            <div><label className="form-label">Min Available Value</label><input type="number" className={controlClass} value={filters.available_value_gte || ""} onChange={(e) => setFilters({ ...filters, available_value_gte: e.target.value })} /></div>
            <div><label className="form-label">Max Available Value</label><input type="number" className={controlClass} value={filters.available_value_lte || ""} onChange={(e) => setFilters({ ...filters, available_value_lte: e.target.value })} /></div>
            <div><label className="form-label">Is Restricted</label><select className={controlClass} value={filters.is_restricted || "all"} onChange={(e) => setFilters({ ...filters, is_restricted: e.target.value })}><option value="all">All</option><option value="true">Restricted</option><option value="false">Not Restricted</option></select></div>
            <div><label className="form-label">Purchase Status</label><Select isMulti value={filters.purchase_status ? filters.purchase_status.split(',').map(s => purchaseStatusOptions.find(o => o.value === s) || { value: s, label: s }) : []} onChange={(selected) => setFilters({ ...filters, purchase_status: selected ? selected.map(s => s.value).join(',') : "" })} options={purchaseStatusOptions} placeholder="All" className="basic-multi-select" classNamePrefix="select" /></div>
            <div className="sm:col-span-2"><DateRangeFilter label="Expiry Date" fromValue={filters.expiry_date_from || ""} toValue={filters.expiry_date_to || ""} onFromChange={(v) => setFilters({ ...filters, expiry_date_from: v })} onToChange={(v) => setFilters({ ...filters, expiry_date_to: v })} onClear={() => setFilters({ ...filters, expiry_date_from: "", expiry_date_to: "" })} /></div>
        </FilterGrid>
    </FilterPanel></div>;
}
