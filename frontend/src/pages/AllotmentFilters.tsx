import { useMemo } from "react";
import { Box, TextField, MenuItem, Typography, useTheme, Chip, Stack } from "@mui/material";
import Select from "react-select";
import HybridSelect from "../components/HybridSelect";
import DateRangeFilter from "../components/DateRangeFilter";
import { FilterPanel, FilterField } from "../components/filters/FilterPanel";

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

// Custom MultiValue component for compact multi-select display
function CompactMultiValue({ data, removeProps }: any) {
    return (
        <Chip
            label={data.label}
            onDelete={() => removeProps.onClick()}
            size="small"
            variant="outlined"
            sx={{ height: 28, fontSize: '0.8rem' }}
        />
    );
}

// Custom ValueContainer for compact display of many values
function CompactValueContainer({ children, ...props }: any) {
    const selectedValues = props.getValue ? props.getValue() : [];
    const maxVisible = 2;
    const moreCount = Math.max(0, selectedValues.length - maxVisible);

    return (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center', minHeight: '44px', padding: '4px 8px' }}>
            {children.slice(0, (selectedValues.length > 0 ? maxVisible * 2 : 0) + (moreCount > 0 ? 0 : 1))}
            {moreCount > 0 && (
                <Chip
                    label={`+${moreCount} more`}
                    size="small"
                    variant="outlined"
                    sx={{ height: 28, fontSize: '0.75rem', pointerEvents: 'none' }}
                />
            )}
        </div>
    );
}

export default function AllotmentFilters({
    filters,
    setFilters,
    availableItemNames,
    notificationOptions,
    purchaseStatusOptions,
    routePlanningTarget,
    defaultSearchMode = "ACTUAL",
    defaultItemId = null
}: AllotmentFiltersProps) {
    const muiTheme = useTheme();
    const isPlanMode = filters.debit_based_on === "PLAN";
    const defaults = useMemo(() => ({
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
        debit_based_on: defaultSearchMode,
    }), [defaultItemId, defaultSearchMode, purchaseStatusOptions]);

    const itemLabel = isPlanMode ? "Filter By Planning Target Item" : "Filter By Actual Item Name";

    // Shared react-select styles for consistent height (44px)
    const selectStyles = {
        control: (base: any) => ({
            ...base,
            minHeight: '44px',
            height: 'auto',
            borderColor: muiTheme.palette.divider,
            padding: '2px 0',
        }),
        menu: (base: any) => ({
            ...base,
            zIndex: 9999,
        }),
        valueContainer: (base: any) => ({
            ...base,
            maxHeight: '100%',
            padding: '4px 8px',
        }),
        multiValue: (base: any) => ({
            ...base,
            fontSize: '0.875rem',
            margin: '2px',
        }),
        multiValueLabel: (base: any) => ({
            ...base,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
        }),
    };

    return (
        <Box sx={{ mb: 3 }}>
            <FilterPanel onFiltersChange={() => {}}>
                    {/* Row 1: License Number, Item, Norm Class, Exporter */}
                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }} component="label" htmlFor="license-number">License Number</Typography>
                        <TextField
                            id="license-number"
                            size="small"
                            placeholder="Search licence…"
                            value={filters.license_number || ""}
                            onChange={(e) => setFilters({ ...filters, license_number: e.target.value })}
                            fullWidth
                            variant="outlined"
                        />
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>{itemLabel}</Typography>
                        <Select
                            value={filters.item_id ? availableItemNames.find(i => String(i.value) === String(filters.item_id)) || { value: filters.item_id, label: filters.item_id } : null}
                            onChange={(selected) => setFilters({ ...filters, item_id: selected ? String(selected.value) : "" })}
                            options={availableItemNames}
                            placeholder="Select item"
                            isClearable
                            isDisabled={isPlanMode && Boolean(routePlanningTarget)}
                            styles={selectStyles}
                            classNamePrefix="react-select"
                        />
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Norm Class</Typography>
                        <HybridSelect
                            fieldMeta={{ endpoint: "masters/sion-classes/?is_active=true", label_field: "norm_class" }}
                            value={filters.norm_class}
                            onChange={(value) => setFilters({ ...filters, norm_class: value as string })}
                            placeholder="All"
                            isClearable
                        />
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Exporter</Typography>
                        <HybridSelect
                            fieldMeta={{ endpoint: "masters/companies/", label_field: "name" }}
                            value={filters.exporter}
                            onChange={(value) => setFilters({ ...filters, exporter: value as string })}
                            placeholder="All"
                            isClearable
                        />
                    </FilterField>

                    {/* Row 2: Quantities */}
                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }} component="label" htmlFor="min-available-qty">Min Available Qty</Typography>
                        <TextField
                            id="min-available-qty"
                            size="small"
                            type="number"
                            placeholder="0"
                            value={filters.available_quantity_gte || ""}
                            onChange={(e) => setFilters({ ...filters, available_quantity_gte: e.target.value })}
                            fullWidth
                            variant="outlined"
                        />
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Max Available Qty</Typography>
                        <TextField
                            size="small"
                            type="number"
                            placeholder="No limit"
                            value={filters.available_quantity_lte || ""}
                            onChange={(e) => setFilters({ ...filters, available_quantity_lte: e.target.value })}
                            fullWidth
                            variant="outlined"
                        />
                    </FilterField>

                    {/* Row 3: Values */}
                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }} component="label" htmlFor="min-available-value">Min Available Value</Typography>
                        <TextField
                            id="min-available-value"
                            size="small"
                            type="number"
                            placeholder="0"
                            value={filters.available_value_gte || ""}
                            onChange={(e) => setFilters({ ...filters, available_value_gte: e.target.value })}
                            fullWidth
                            variant="outlined"
                        />
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Max Available Value</Typography>
                        <TextField
                            size="small"
                            type="number"
                            placeholder="No limit"
                            value={filters.available_value_lte || ""}
                            onChange={(e) => setFilters({ ...filters, available_value_lte: e.target.value })}
                            fullWidth
                            variant="outlined"
                        />
                    </FilterField>

                    {/* Row 4: Status fields */}
                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>License Status</Typography>
                        <TextField
                            select
                            size="small"
                            value={filters.license_status || "active"}
                            onChange={(e) => setFilters({ ...filters, license_status: e.target.value })}
                            fullWidth
                            variant="outlined"
                        >
                            <MenuItem value="all">All</MenuItem>
                            <MenuItem value="active">Active</MenuItem>
                            <MenuItem value="expired">Expired</MenuItem>
                            <MenuItem value="expiring_soon">Expiring Soon</MenuItem>
                        </TextField>
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Debit Based On</Typography>
                        <TextField
                            select
                            size="small"
                            value={filters.debit_based_on || "ACTUAL"}
                            onChange={(e) => setFilters({ ...filters, debit_based_on: e.target.value, item_id: "" })}
                            fullWidth
                            variant="outlined"
                        >
                            <MenuItem value="PLAN">Plan</MenuItem>
                            <MenuItem value="ACTUAL">Actual</MenuItem>
                        </TextField>
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Is Restricted</Typography>
                        <TextField
                            select
                            size="small"
                            value={filters.is_restricted || "all"}
                            onChange={(e) => setFilters({ ...filters, is_restricted: e.target.value })}
                            fullWidth
                            variant="outlined"
                        >
                            <MenuItem value="all">All</MenuItem>
                            <MenuItem value="true">Restricted</MenuItem>
                            <MenuItem value="false">Not Restricted</MenuItem>
                        </TextField>
                    </FilterField>

                    {/* Row 5: Notification & Description */}
                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Notification Number</Typography>
                        <TextField
                            select
                            size="small"
                            value={filters.notification_number || ""}
                            onChange={(e) => setFilters({ ...filters, notification_number: e.target.value })}
                            fullWidth
                            variant="outlined"
                        >
                            <MenuItem value="">All</MenuItem>
                            {notificationOptions.map(option => (
                                <MenuItem key={option.value} value={option.value}>{option.display_name}</MenuItem>
                            ))}
                        </TextField>
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }} component="label" htmlFor="item-description">Item Description</Typography>
                        <TextField
                            id="item-description"
                            size="small"
                            placeholder="Search description"
                            value={filters.description || ""}
                            onChange={(e) => setFilters({ ...filters, description: e.target.value })}
                            fullWidth
                            variant="outlined"
                        />
                    </FilterField>

                    {/* Row 6: Exclude Exporter & HS Code */}
                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Exclude Exporter</Typography>
                        <HybridSelect
                            fieldMeta={{ endpoint: "masters/companies/", label_field: "name" }}
                            value={filters.exclude_exporter}
                            onChange={(value) => setFilters({ ...filters, exclude_exporter: value as string })}
                            placeholder="None"
                            isClearable
                        />
                    </FilterField>

                    <FilterField>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }} component="label" htmlFor="hs-code">HS Code</Typography>
                        <TextField
                            id="hs-code"
                            size="small"
                            placeholder="Filter by HS code"
                            value={filters.hs_code || ""}
                            onChange={(e) => setFilters({ ...filters, hs_code: e.target.value })}
                            fullWidth
                            variant="outlined"
                        />
                    </FilterField>

                    {/* Row 7: Purchase Status (spans 2 columns for multi-select) */}
                    <FilterField wide>
                        <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.75 }}>Purchase Status</Typography>
                        <Select
                            isMulti
                            value={filters.purchase_status ? filters.purchase_status.split(',').map(s => purchaseStatusOptions.find(o => o.value === s) || { value: s, label: s }) : []}
                            onChange={(selected) => setFilters({ ...filters, purchase_status: selected ? selected.map(s => s.value).join(',') : "" })}
                            options={purchaseStatusOptions}
                            placeholder="All"
                            styles={selectStyles}
                            components={{
                                MultiValue: CompactMultiValue,
                                ValueContainer: CompactValueContainer,
                            }}
                            classNamePrefix="react-select"
                        />
                    </FilterField>

                    {/* Row 8: Expiry Date (spans 2 columns) */}
                    <FilterField wide>
                        <DateRangeFilter
                            label="Expiry Date"
                            fromValue={filters.expiry_date_from || ""}
                            toValue={filters.expiry_date_to || ""}
                            onFromChange={(v) => setFilters({ ...filters, expiry_date_from: v })}
                            onToChange={(v) => setFilters({ ...filters, expiry_date_to: v })}
                            onClear={() => setFilters({ ...filters, expiry_date_from: "", expiry_date_to: "" })}
                        />
                    </FilterField>
            </FilterPanel>
        </Box>
    );
}
