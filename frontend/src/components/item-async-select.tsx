import DebouncedAsyncSelect from "./DebouncedAsyncSelect";

type ItemNameAsyncSelectProps = {
    value: number | null;
    onChange: (itemId: number | null) => void;
    disabled?: boolean;
    placeholder?: string;
};

export function ItemNameAsyncSelect({ value, onChange, disabled = false, placeholder = "Search item..." }: ItemNameAsyncSelectProps) {
    return (
        <DebouncedAsyncSelect
            endpoint="masters/item-names/"
            labelField="name"
            valueField="id"
            value={value}
            onChange={(selected) => {
                if (selected && typeof selected === "object" && "value" in selected) {
                    onChange(selected.value as number);
                } else {
                    onChange(null);
                }
            }}
            placeholder={placeholder}
            isClearable={true}
            isDisabled={disabled}
            debounceDelay={300}
        />
    );
}
