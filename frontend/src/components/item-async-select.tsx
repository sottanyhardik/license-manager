import DebouncedAsyncSelect from "./DebouncedAsyncSelect";

type ItemNameAsyncSelectProps = {
    value: number | null;
    /** `label` is the chosen option's display name (null when cleared). */
    onChange: (itemId: number | null, label?: string | null) => void;
    disabled?: boolean;
    placeholder?: string;
    ariaLabel?: string;
    autoFocus?: boolean;
    /** Render the menu in document.body so a table's overflow container cannot clip it. */
    portalMenu?: boolean;
};

export function ItemNameAsyncSelect({
    value,
    onChange,
    disabled = false,
    placeholder = "Search item...",
    ariaLabel,
    autoFocus = false,
    portalMenu = false,
}: ItemNameAsyncSelectProps) {
    return (
        <DebouncedAsyncSelect
            endpoint="masters/item-names/"
            labelField="name"
            valueField="id"
            value={value}
            onChange={(selected: unknown, option?: { label?: string } | null) => {
                // DebouncedAsyncSelect hands back the raw value (id); also accept an option object.
                if (typeof selected === "number") {
                    onChange(selected, option?.label ?? null);
                } else if (selected && typeof selected === "object" && "value" in selected) {
                    onChange((selected as { value: number }).value, (selected as { label?: string }).label ?? null);
                } else {
                    onChange(null, null);
                }
            }}
            placeholder={placeholder}
            isClearable={true}
            isDisabled={disabled}
            debounceDelay={300}
            ariaLabel={ariaLabel}
            autoFocus={autoFocus}
            portalMenu={portalMenu}
        />
    );
}
