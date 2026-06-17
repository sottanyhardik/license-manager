import Select from "react-select";
import AsyncSelectField from "./AsyncSelectField";
import type { FieldMeta, SelectOption } from "../types";

interface HybridSelectProps {
    fieldMeta?: FieldMeta;
    value?: unknown;
    onChange: (value: unknown) => void;
    isMulti?: boolean;
    placeholder?: string;
    isClearable?: boolean;
    isDisabled?: boolean;
    staticOptions?: SelectOption[] | null;
    className?: string;
    formatLabel?: ((item: Record<string, unknown>) => string) | null;
}

/**
 * HybridSelect Component - Intelligently chooses between static Select and AsyncSelect
 */
export default function HybridSelect({
    fieldMeta = {},
    value,
    onChange,
    isMulti = false,
    placeholder = "Select...",
    isClearable = true,
    isDisabled = false,
    staticOptions = null,
    className = "",
    formatLabel: customFormatLabel = null,
}: HybridSelectProps) {
    const useAsync = Boolean(fieldMeta.endpoint || fieldMeta.fk_endpoint);
    const hasChoices = Boolean(staticOptions || fieldMeta.choices);

    if (useAsync) {
        const endpoint = (fieldMeta.endpoint || fieldMeta.fk_endpoint)!;
        const labelField = fieldMeta.label_field || "name";
        const valueField = fieldMeta.value_field || "id";

        const defaultFormatLabel = (item: Record<string, unknown>) => {
            if (endpoint.includes("hs-code")) {
                return String(item.hs_code || item.name || item.id || "");
            }
            if (endpoint.includes("port")) {
                return String(item.name || item.code || item.id || "");
            }
            return String(item[labelField] || item.name || item.id || "");
        };

        const formatLabel = customFormatLabel || defaultFormatLabel;

        return (
            <AsyncSelectField
                endpoint={endpoint}
                labelField={labelField}
                valueField={valueField}
                value={value}
                onChange={onChange}
                isMulti={isMulti}
                placeholder={placeholder}
                isClearable={isClearable}
                isDisabled={isDisabled}
                formatLabel={formatLabel}
                className={className}
                loadOnMount={true}
            />
        );
    }

    if (hasChoices) {
        let options: SelectOption[] = staticOptions || [];

        if (!staticOptions && fieldMeta.choices) {
            options = fieldMeta.choices.map(choice => {
                if (Array.isArray(choice)) {
                    return { value: choice[0], label: choice[1] };
                }
                if (typeof choice === "object") {
                    return { value: (choice as SelectOption).value, label: (choice as SelectOption).label };
                }
                return { value: String(choice), label: String(choice) };
            });
        }

        let selectedOption: SelectOption | SelectOption[] | null = null;
        if (isMulti) {
            const values = Array.isArray(value) ? value : (value ? [value] : []);
            selectedOption = options.filter(opt => (values as unknown[]).includes(opt.value));
        } else {
            selectedOption = options.find(opt => opt.value === value) || null;
        }

        const handleChange = (selected: SelectOption | SelectOption[] | null) => {
            if (isMulti) {
                const arr = selected as SelectOption[] | null;
                onChange(arr ? arr.map(opt => opt.value) : []);
            } else {
                const single = selected as SelectOption | null;
                onChange(single ? single.value : null);
            }
        };

        return (
            <Select
                options={options}
                value={selectedOption}
                onChange={handleChange as (value: unknown) => void}
                isMulti={isMulti}
                isClearable={isClearable}
                isDisabled={isDisabled}
                placeholder={placeholder}
                className={className}
                classNamePrefix="react-select"
                styles={{
                    control: (base) => ({
                        ...base,
                        minHeight: "38px",
                        borderColor: "var(--tb-border)",
                    }),
                    menu: (base) => ({ ...base, zIndex: 9999 }),
                }}
            />
        );
    }

    return (
        <input
            type="text"
            className="react-select-container"
            value={String(value || "")}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={isDisabled}
        />
    );
}
