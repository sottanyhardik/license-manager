import CreatableSelect from "react-select/creatable";
import type { ClipboardEvent } from "react";

type ChipOption = { label: string; value: string };

const toOptions = (values: string[]): ChipOption[] => values.map((v) => ({ label: v, value: v }));

/**
 * Chip/tag input for excluding one or more license numbers — reuses
 * `react-select`'s `CreatableSelect` (already a dependency via
 * `AsyncSelectField`) purely as a freeform multi-value input: no options
 * list, so every typed value becomes a removable chip on Enter/Tab/comma.
 * `classNamePrefix="react-select"` picks up the existing chip styling
 * (`.react-select__multi-value*`, `App.css`) for free — no new CSS needed.
 *
 * Supports comma-separated paste (splits into multiple chips at once) in
 * addition to react-select's built-in Enter/Tab-to-create and per-chip
 * remove button.
 */
export default function ExcludeLicenseNumberInput({
    id,
    value,
    onChange,
    placeholder = "e.g. 0311051359, 0311051360",
}: {
    id?: string;
    value: string[];
    onChange: (values: string[]) => void;
    placeholder?: string;
}) {
    const addValues = (raw: string) => {
        const additions = raw
            .split(",")
            .map((v) => v.trim())
            .filter(Boolean);
        if (!additions.length) return;
        onChange(Array.from(new Set([...value, ...additions])));
    };

    return (
        <div
            onPaste={(e: ClipboardEvent<HTMLDivElement>) => {
                const text = e.clipboardData.getData("text");
                if (text.includes(",")) {
                    e.preventDefault();
                    addValues(text);
                }
            }}
        >
            <CreatableSelect<ChipOption, true>
                inputId={id}
                isMulti
                isClearable
                classNamePrefix="react-select"
                placeholder={placeholder}
                value={toOptions(value)}
                onChange={(selected) => onChange((selected ?? []).map((o) => o.value))}
                onCreateOption={(inputValue) => addValues(inputValue)}
                components={{ DropdownIndicator: () => null }}
                formatCreateLabel={(inputValue) => `Add "${inputValue}"`}
            />
        </div>
    );
}
