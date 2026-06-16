import { useState, useEffect, useRef } from "react";
import { Search, X, Loader2 } from "lucide-react";
import { useDebouncedState } from "../hooks/useDebounce";

/**
 * Debounced search input — fires onChange only after the user stops typing.
 * Debounce logic preserved exactly; Bootstrap input-group replaced with Tailwind.
 */
export default function DebouncedSearchInput({
    value,
    onChange,
    delay = 500,
    placeholder = "Search...",
    className = "",
    style = {},
    showPendingIndicator = true,
}) {
    const [localValue, setLocalValue] = useState(value);
    const { debouncedValue, isPending } = useDebouncedState(localValue, delay);

    const valueRef = useRef(value);
    const onChangeRef = useRef(onChange);
    useEffect(() => { valueRef.current = value; onChangeRef.current = onChange; });

    useEffect(() => { setLocalValue(value); }, [value]);

    useEffect(() => {
        if (debouncedValue !== valueRef.current) onChangeRef.current(debouncedValue);
    }, [debouncedValue]);

    return (
        <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-muted-foreground">
                <Search className="size-4" />
            </span>
            <input
                type="text"
                className={`flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 pl-8 text-sm shadow-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-[3px] ${className}`}
                placeholder={placeholder}
                value={localValue}
                onChange={(e) => setLocalValue(e.target.value)}
                style={style}
            />
            {localValue && (
                <button
                    type="button"
                    onClick={() => { setLocalValue(""); onChange(""); }}
                    className="absolute inset-y-0 right-0 flex w-8 cursor-pointer items-center justify-center border-0 bg-transparent text-muted-foreground hover:text-foreground"
                    style={{ zIndex: 10 }}
                >
                    <X className="size-3.5" />
                </button>
            )}
            {showPendingIndicator && isPending && (
                <span className="pointer-events-none absolute inset-y-0 right-8 flex items-center">
                    <Loader2 className="size-3.5 animate-spin text-primary" />
                </span>
            )}
        </div>
    );
}
