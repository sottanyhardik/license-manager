import { useMemo, useState } from "react";
import Select from "react-select";
import HybridSelect from "../components/HybridSelect";
import DateRangeFilter from "../components/DateRangeFilter";
import { ChevronDown, Filter, SlidersHorizontal, X, XCircle } from "lucide-react";

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
    const [moreFiltersOpen, setMoreFiltersOpen] = useState(false);
    const isPlanMode = filters.debit_based_on === "PLAN";
    const defaults = useMemo(() => ({
        description: "", exporter: "", exclude_exporter: "", license_number: "", available_quantity_gte: "50", available_quantity_lte: "", available_value_gte: "100", available_value_lte: "", notification_number: "", norm_class: "", hs_code: "", is_expired: "all", is_restricted: "all", purchase_status: purchaseStatusOptions.map(o => o.value).join(','), license_status: "active", item_id: defaultItemId == null ? "" : String(defaultItemId), expiry_date_from: "", expiry_date_to: "", debit_based_on: defaultSearchMode,
    }), [defaultItemId, defaultSearchMode, purchaseStatusOptions]);
    const secondaryFields = ["notification_number", "description", "exclude_exporter", "hs_code", "available_quantity_lte", "available_value_gte", "available_value_lte", "is_restricted", "purchase_status", "expiry_date_from", "expiry_date_to"];
    const labels: Record<string, string> = { notification_number: "Notification", description: "Description", exclude_exporter: "Exclude Exporter", hs_code: "HS Code", available_quantity_lte: "Max Qty", available_value_gte: "Min Value", available_value_lte: "Max Value", is_restricted: "Restricted", purchase_status: "Purchase Status", expiry_date_from: "Expiry From", expiry_date_to: "Expiry To", license_number: "License Number", item_id: "Item", norm_class: "Norm Class", exporter: "Exporter", available_quantity_gte: "Min Qty", license_status: "License Status", debit_based_on: "Debit Based On" };
    const optionLabel = (field: string, value: string) => {
        if (field === "notification_number") return notificationOptions.find(option => option.value === value)?.display_name || value;
        if (field === "purchase_status") return value.split(',').map(item => purchaseStatusOptions.find(option => option.value === item)?.label || item).join(', ');
        if (field === "is_restricted") return value === "true" ? "Restricted" : value === "false" ? "Not restricted" : value;
        return value;
    };
    const activeSecondary = secondaryFields.filter(field => String(filters[field] ?? "") !== String(defaults[field] ?? ""));
    const activePrimary = ["license_number", "item_id", "norm_class", "exporter", "available_quantity_gte", "license_status", "debit_based_on"].filter(field => String(filters[field] ?? "") !== String(defaults[field] ?? ""));
    const chips = [...activePrimary, ...activeSecondary];
    const clearField = (field: string) => setFilters({ ...filters, [field]: defaults[field] });
    const itemLabel = isPlanMode ? "Filter By Planning Target Item" : "Filter By Actual Item Name";

    return <section className="mb-3 overflow-hidden rounded-lg border border-border/60 bg-card" aria-label="Available licence filters">
        <div className="flex flex-wrap items-end gap-2 px-3 py-2.5">
            <div className="flex items-center gap-1.5 pb-1 text-[11px] font-bold uppercase tracking-[0.08em] text-muted-foreground"><Filter className="size-3.5" aria-hidden="true" /> Filters</div>
            <div className="min-w-[150px] flex-1 sm:max-w-[190px]"><label className="form-label text-[11px]">License Number</label><input className={controlClass} placeholder="Search licence…" value={filters.license_number || ""} onChange={(e) => setFilters({ ...filters, license_number: e.target.value })} /></div>
            <div className="min-w-[190px] flex-[1.25]"><label className="form-label text-[11px]">{itemLabel}</label><Select value={filters.item_id ? availableItemNames.find(i => String(i.value) === String(filters.item_id)) || { value: filters.item_id, label: filters.item_id } : null} onChange={(selected) => setFilters({ ...filters, item_id: selected ? String(selected.value) : "" })} options={availableItemNames} placeholder={isPlanMode ? "Planning item" : "Actual item"} className="basic-multi-select text-[13px]" classNamePrefix="select" isDisabled={isPlanMode && Boolean(routePlanningTarget)} /></div>
            <div className="min-w-[130px] flex-1"><label className="form-label text-[11px]">Norm Class</label><HybridSelect fieldMeta={{ endpoint: "masters/sion-classes/?is_active=true", label_field: "norm_class" }} value={filters.norm_class} onChange={(value) => setFilters({ ...filters, norm_class: value as string })} placeholder="All" isClearable /></div>
            <div className="min-w-[140px] flex-1"><label className="form-label text-[11px]">Exporter</label><HybridSelect fieldMeta={{ endpoint: "masters/companies/", label_field: "name" }} value={filters.exporter} onChange={(value) => setFilters({ ...filters, exporter: value as string })} placeholder="All" isClearable /></div>
            <div className="w-[94px]"><label className="form-label text-[11px]">Min Available Qty</label><input type="number" className={controlClass} value={filters.available_quantity_gte || ""} onChange={(e) => setFilters({ ...filters, available_quantity_gte: e.target.value })} /></div>
            <div className="w-[116px]"><label className="form-label text-[11px]">Licence Status</label><select className={controlClass} value={filters.license_status || "active"} onChange={(e) => setFilters({ ...filters, license_status: e.target.value })}><option value="all">All</option><option value="active">Active</option><option value="expired">Expired</option><option value="expiring_soon">Expiring Soon</option></select></div>
            <div className="w-[102px]"><label className="form-label text-[11px]">Debit Based On</label><select className={controlClass} value={filters.debit_based_on || "PLAN"} onChange={(e) => setFilters({ ...filters, debit_based_on: e.target.value, item_id: "" })}><option value="PLAN">Plan</option><option value="ACTUAL">Actual</option></select></div>
            <button type="button" onClick={() => setMoreFiltersOpen(open => !open)} aria-expanded={moreFiltersOpen} className="inline-flex h-8 items-center gap-1 rounded-md border border-border bg-muted/30 px-2 text-xs font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><SlidersHorizontal className="size-3.5" aria-hidden="true" /> More Filters{activeSecondary.length > 0 && ` (${activeSecondary.length})`}<ChevronDown className={moreFiltersOpen ? "size-3.5 rotate-180" : "size-3.5"} aria-hidden="true" /></button>
            <button type="button" onClick={() => setFilters(defaults)} className="inline-flex h-8 items-center gap-1 rounded-md px-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><XCircle className="size-3.5" aria-hidden="true" /> Clear</button>
        </div>
        {chips.length > 0 && <div className="flex flex-wrap gap-1.5 border-t border-border/50 bg-muted/20 px-3 py-1.5" aria-label="Active filters">{chips.map(field => <span key={field} className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-2 py-0.5 text-[11px] text-foreground"><span className="text-muted-foreground">{labels[field] || field}:</span> {optionLabel(field, String(filters[field] ?? ""))}<button type="button" aria-label={`Remove ${labels[field] || field} filter`} onClick={() => clearField(field)} className="rounded-full p-0.5 hover:bg-primary/10"><X className="size-3" /></button></span>)}</div>}
        {moreFiltersOpen && <div className="grid grid-cols-1 gap-2 border-t border-border/60 bg-muted/20 p-3 sm:grid-cols-2 lg:grid-cols-4">
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
        </div>}
    </section>;
}
